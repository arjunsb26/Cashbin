"""The fixed asset rollforward: opening, movements, closing, and that it ties.

The register in this fixture holds four assets on purpose: one bought long ago and
still in use, one bought inside the period, one thrown away inside the period, and
one that went years ago and should not appear in this period's movements at all.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import session_scope
from app.engine import depreciation
from app.ledger import rollforward
from app.ledger.close import to_asset_info

PERIOD_START = "2026-09-01"
PERIOD_END = "2026-09-30"


def _asset(
    session: Session,
    tag: str,
    description: str,
    cost_cents: int,
    in_service: str,
    life: int,
    *,
    tax_method: models.TaxMethod = models.TaxMethod.straight_line,
    status: models.AssetStatus = models.AssetStatus.active,
    salvage_cents: int = 0,
    tax_basis_cents_override: int | None = None,
) -> models.Asset:
    row = models.Asset(
        tag=tag,
        description=description,
        cost_cents=cost_cents,
        in_service_date=in_service,
        book_life_months=life,
        salvage_cents=salvage_cents,
        tax_method=tax_method,
        tax_basis_cents_override=tax_basis_cents_override,
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def _disposal(
    session: Session,
    asset: models.Asset,
    day: str,
    *,
    label: str,
    book_value_cents: int,
    tax_basis_cents: int,
    proceeds_cents: int = 0,
) -> models.Event:
    event = models.Event(
        created_at=f"{day}T12:00:00+00:00",
        kind=models.EventKind.toss,
        mass_g=900.0,
        mass_err_g=1.0,
        status=models.EventStatus.posted,
    )
    session.add(event)
    session.flush()
    session.add(
        models.ItemRecord(
            event_id=event.id,
            label=label,
            item_class=models.ItemClass.fixed_asset,
            mass_g=900.0,
            condition="unknown",
            material_mix_json=json.dumps({"mixed_plastics": 1.0}),
            regulatory_flags_json=json.dumps([]),
            book_value_cents=book_value_cents,
            tax_basis_cents=tax_basis_cents,
            asset_id=asset.id,
        )
    )
    asset.status = models.AssetStatus.disposed
    asset.disposed_event_id = event.id
    session.add(
        models.JournalEntry(
            event_id=event.id,
            memo=f"Dispose of {asset.description} ({asset.tag})",
            basis=models.JournalBasis.book,
            evidence_json=json.dumps(
                {
                    "event_id": event.id,
                    "asset_id": asset.id,
                    "asset_tag": asset.tag,
                    "cost_cents": asset.cost_cents,
                    "book_value_cents": book_value_cents,
                    "proceeds_cents": proceeds_cents,
                    "gain_cents": proceeds_cents - book_value_cents,
                }
            ),
        )
    )
    session.flush()
    return event


def build_register(session: Session) -> dict[str, Any]:
    """Four assets: one held, one added, one disposed, one gone before the period."""
    held = _asset(session, "bb-0001", "espresso machine", 240_000, "2024-09-01", 60)
    added = _asset(session, "bb-0002", "label printer", 36_000, "2026-09-10", 36)
    leaving = _asset(session, "bb-0003", "mechanical keyboard", 12_000, "2024-03-01", 36)
    gone = _asset(
        session, "bb-0004", "old monitor", 30_000, "2020-01-01", 36,
        status=models.AssetStatus.active,
    )
    _disposal(
        session, leaving, "2026-09-15", label="mechanical keyboard",
        book_value_cents=2_000, tax_basis_cents=2_000,
    )
    _disposal(
        session, gone, "2025-04-04", label="old monitor",
        book_value_cents=0, tax_basis_cents=0,
    )
    session.commit()
    return {
        "held": held.id,
        "added": added.id,
        "leaving": leaving.id,
        "gone": gone.id,
    }


def _block(session: Session) -> Any:
    return rollforward.compute(session, PERIOD_START, PERIOD_END)


def test_every_row_ties_opening_plus_movements_to_closing(settings: Settings) -> None:
    with session_scope() as session:
        build_register(session)
        block = _block(session)

    for row in [*block.rows, block.total]:
        assert (
            row.closing_cost_cents
            == row.opening_cost_cents + row.additions_cents - row.disposals_cost_cents
        ), row.tag
        assert (
            row.closing_accum_cents
            == row.opening_accum_cents + row.depreciation_cents - row.disposals_accum_cents
        ), row.tag
        assert row.opening_nbv_cents == row.opening_cost_cents - row.opening_accum_cents
        assert row.closing_nbv_cents == row.closing_cost_cents - row.closing_accum_cents
    assert block.ties is True


def test_the_total_is_the_sum_of_the_rows(settings: Settings) -> None:
    with session_scope() as session:
        build_register(session)
        block = _block(session)

    for field in (
        "opening_cost_cents",
        "additions_cents",
        "disposals_cost_cents",
        "closing_cost_cents",
        "opening_accum_cents",
        "depreciation_cents",
        "disposals_accum_cents",
        "closing_accum_cents",
    ):
        assert getattr(block.total, field) == sum(
            getattr(row, field) for row in block.rows
        ), field


def test_an_asset_held_all_period_only_depreciates(settings: Settings) -> None:
    with session_scope() as session:
        ids = build_register(session)
        block = _block(session)
        asset = session.get(models.Asset, ids["held"])
        assert asset is not None
        info = to_asset_info(asset)

    row = next(r for r in block.rows if r.asset_id == ids["held"])
    assert row.opening_cost_cents == 240_000
    assert row.additions_cents == 0
    assert row.disposals_cost_cents == 0
    assert row.closing_cost_cents == 240_000
    # Straight line, month based, read from depreciation.py rather than retyped here.
    opening = depreciation.book_value(info, date.fromisoformat(PERIOD_START)).accum_cents
    closing = depreciation.book_value(info, date.fromisoformat(PERIOD_END)).accum_cents
    assert row.opening_accum_cents == opening
    assert row.closing_accum_cents == closing
    assert row.depreciation_cents == closing - opening


def test_an_asset_bought_in_the_period_is_an_addition(settings: Settings) -> None:
    with session_scope() as session:
        ids = build_register(session)
        block = _block(session)

    row = next(r for r in block.rows if r.asset_id == ids["added"])
    assert row.opening_cost_cents == 0
    assert row.additions_cents == 36_000
    assert row.closing_cost_cents == 36_000
    assert row.opening_accum_cents == 0
    assert row.opening_nbv_cents == 0


def test_a_disposal_takes_its_cost_and_its_accumulated_depreciation_out(
    settings: Settings,
) -> None:
    with session_scope() as session:
        ids = build_register(session)
        block = _block(session)

    row = next(r for r in block.rows if r.asset_id == ids["leaving"])
    assert row.opening_cost_cents == 12_000
    assert row.disposals_cost_cents == 12_000
    assert row.closing_cost_cents == 0
    assert row.disposals_accum_cents > 0
    assert row.closing_accum_cents == 0
    assert row.closing_nbv_cents == 0


def test_an_asset_disposed_before_the_period_does_not_move(settings: Settings) -> None:
    with session_scope() as session:
        ids = build_register(session)
        block = _block(session)

    row = next(r for r in block.rows if r.asset_id == ids["gone"])
    assert row.opening_cost_cents == 0
    assert row.additions_cents == 0
    assert row.disposals_cost_cents == 0
    assert row.closing_cost_cents == 0
    assert row.depreciation_cents == 0


def test_an_empty_register_still_comes_back_whole(settings: Settings) -> None:
    with session_scope() as session:
        block = _block(session)

    assert block.rows == []
    assert block.total.closing_cost_cents == 0
    assert block.ties is True
    assert block.period_start == PERIOD_START
