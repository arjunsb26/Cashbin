"""Book to tax on disposals, in the M-1 shape, with the reason for every gap.

Two assets leave in the period: one written off in full on the day it was bought,
one on straight line. The first is where book and tax disagree and the second is
where they do not, which is exactly the pair that proves the bridge closes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import session_scope
from app.ledger import reconciliation
from tests.test_ledger_rollforward import (
    PERIOD_END,
    PERIOD_START,
    _asset,
    _disposal,
)


def build_disposals(session: Session) -> dict[str, int]:
    """One bonus asset and one straight line asset, both leaving in the period."""
    bonus = _asset(
        session, "bb-0020", "laptop", 180_000, "2025-02-01", 36,
        tax_method=models.TaxMethod.bonus_100,
    )
    plain = _asset(
        session, "bb-0021", "mechanical keyboard", 12_000, "2024-03-01", 36,
        tax_method=models.TaxMethod.straight_line,
    )
    bonus_event = _disposal(
        session, bonus, "2026-09-12", label="laptop",
        book_value_cents=85_000, tax_basis_cents=0,
    )
    plain_event = _disposal(
        session, plain, "2026-09-15", label="mechanical keyboard",
        book_value_cents=2_000, tax_basis_cents=2_000,
    )
    session.commit()
    return {
        "bonus": bonus.id,
        "plain": plain.id,
        "bonus_event": bonus_event.id,
        "plain_event": plain_event.id,
    }


def _block(session: Session) -> reconciliation.Any:  # type: ignore[name-defined]
    return reconciliation.compute(session, PERIOD_START, PERIOD_END)


def test_the_bridge_closes_to_zero(settings: Settings) -> None:
    with session_scope() as session:
        build_disposals(session)
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    # Book loss on disposals, less the differences, equals the tax loss on disposals.
    assert block.book_loss_cents - block.differences_cents == block.tax_loss_cents
    assert block.ties is True
    assert block.book_loss_cents == 87_000
    assert block.tax_loss_cents == 2_000
    assert block.differences_cents == 85_000


def test_a_bonus_asset_says_which_year_took_the_deduction(settings: Settings) -> None:
    with session_scope() as session:
        ids = build_disposals(session)
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    row = next(r for r in block.rows if r.asset_id == ids["bonus"])
    assert row.book_loss_cents == 85_000
    assert row.tax_loss_cents == 0
    assert row.difference_cents == 85_000
    assert row.reason == "bonus_100 taken in 2025"
    assert "BONUS_100" in row.rule_ids


def test_a_straight_line_asset_has_no_difference(settings: Settings) -> None:
    with session_scope() as session:
        ids = build_disposals(session)
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    row = next(r for r in block.rows if r.asset_id == ids["plain"])
    assert row.book_loss_cents == 2_000
    assert row.tax_loss_cents == 2_000
    assert row.difference_cents == 0
    assert row.reason == "straight line, no difference"


def test_an_override_says_so(settings: Settings) -> None:
    with session_scope() as session:
        asset = _asset(
            session, "bb-0022", "tablet", 60_000, "2024-06-01", 36,
            tax_method=models.TaxMethod.straight_line,
            tax_basis_cents_override=500,
        )
        _disposal(
            session, asset, "2026-09-20", label="tablet",
            book_value_cents=20_000, tax_basis_cents=500,
        )
        session.commit()
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    row = block.rows[0]
    assert row.reason == "override"
    assert row.difference_cents == 19_500
    assert block.book_loss_cents - block.differences_cents == block.tax_loss_cents


def test_a_period_with_no_disposals_still_ties(settings: Settings) -> None:
    with session_scope() as session:
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    assert block.rows == []
    assert block.book_loss_cents == 0
    assert block.tax_loss_cents == 0
    assert block.ties is True
    assert block.title


def test_a_disposal_outside_the_period_is_not_in_it(settings: Settings) -> None:
    with session_scope() as session:
        asset = _asset(session, "bb-0023", "old monitor", 30_000, "2020-01-01", 36)
        _disposal(
            session, asset, "2025-04-04", label="old monitor",
            book_value_cents=1_000, tax_basis_cents=1_000,
        )
        session.commit()
        block = reconciliation.compute(session, PERIOD_START, PERIOD_END)

    assert block.rows == []
