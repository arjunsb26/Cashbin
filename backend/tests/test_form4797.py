"""The Form 4797 schedule: abandonments in Part II, sales in Part III."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import session_scope
from app.engine import rules
from app.ledger import form4797
from tests.test_ledger_reconciliation import build_disposals
from tests.test_ledger_rollforward import PERIOD_END, PERIOD_START, _asset, _disposal


def _sale(session: Session) -> int:
    """An asset sold for more than its tax basis, which is where recapture lives."""
    asset = _asset(
        session, "bb-0030", "espresso machine", 240_000, "2023-01-01", 60,
        tax_method=models.TaxMethod.straight_line,
    )
    _disposal(
        session, asset, "2026-09-18", label="espresso machine",
        book_value_cents=80_000, tax_basis_cents=80_000, proceeds_cents=110_000,
    )
    session.commit()
    return asset.id


def test_abandonments_land_on_part_ii_line_10(settings: Settings) -> None:
    with session_scope() as session:
        build_disposals(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)

    assert len(block.part_ii_rows) == 2
    assert block.part_iii_rows == []
    for row in block.part_ii_rows:
        assert row.part == "II"
        assert row.line == form4797.PART_II_LINE
        assert row.gross_proceeds_cents == 0
    # The keyboard had 2000 of basis left, the laptop none. A loss reads negative.
    assert block.part_ii_line_10_cents == -2_000


def test_every_row_carries_the_dates_the_cost_and_the_depreciation(
    settings: Settings,
) -> None:
    with session_scope() as session:
        build_disposals(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)

    row = next(r for r in block.part_ii_rows if r.description == "laptop")
    assert row.date_acquired == "2025-02-01"
    assert row.date_disposed == "2026-09-12"
    assert row.cost_cents == 180_000
    # The accumulated depreciation the disposal entry posted, not the cost less the tax
    # basis. Bonus took the whole 1,800.00 in 2025; the books had reached 950.00.
    assert row.depreciation_allowed_cents == 95_000
    assert row.gain_or_loss_cents == 0
    assert "BONUS_100" in row.rule_ids


def test_a_sale_lands_on_part_iii_with_the_recapture_noted(settings: Settings) -> None:
    with session_scope() as session:
        _sale(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)

    assert len(block.part_iii_rows) == 1
    row = block.part_iii_rows[0]
    assert row.part == "III"
    assert row.gross_proceeds_cents == 110_000
    assert row.gain_or_loss_cents == 30_000
    assert "RECAPTURE" in row.rule_ids
    assert "ordinary income" in row.recapture_note
    assert block.part_iii_recapture_cents == 30_000


def test_every_rule_id_is_one_the_rules_file_knows(settings: Settings) -> None:
    with session_scope() as session:
        build_disposals(session)
        _sale(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)

    for row in [*block.part_ii_rows, *block.part_iii_rows]:
        for rule_id in row.rule_ids:
            assert rules.get(rule_id).plain_text


def test_the_schedule_says_what_it_is_not(settings: Settings) -> None:
    with session_scope() as session:
        block = form4797.compute(session, PERIOD_START, PERIOD_END)

    assert block.disclaimer == form4797.DISCLAIMER
    assert block.part_ii_rows == []
    assert block.part_ii_line_10_cents == 0


def _tax_memos(session: Session) -> None:
    """The memo entries the pipeline posts beside every disposal.

    The close reads its tax figures off these. This schedule reads them off the
    item record, which is the row the pipeline wrote them from, so the two agree
    whenever the books are complete. A missing memo is what makes them disagree,
    and that is worth knowing rather than hiding.
    """
    import json

    for record in session.scalars(select(models.ItemRecord)):
        if record.item_class is not models.ItemClass.fixed_asset:
            continue
        session.add(
            models.JournalEntry(
                event_id=record.event_id,
                memo=f"Tax treatment of {record.label}",
                basis=models.JournalBasis.tax_memo,
                evidence_json=json.dumps(
                    {
                        "event_id": record.event_id,
                        "asset_id": record.asset_id,
                        "tax_basis_cents": record.tax_basis_cents,
                        "tax_loss_cents": record.tax_basis_cents,
                        "tax_gain_cents": 0,
                        "rule_ids": ["ABANDON"],
                    }
                ),
            )
        )
    session.commit()


def test_the_line_10_subtotal_matches_the_close(settings: Settings) -> None:
    """The close already reports this subtotal. Two copies that disagree is a bug."""
    from app.ledger import close as close_module

    with session_scope() as session:
        build_disposals(session)
        _tax_memos(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)
        rows = close_module.load_period(session, PERIOD_START, PERIOD_END)
        from app.ledger import queries

        disposals = close_module.asset_disposals(rows, queries.list_entries(session))

    assert block.part_ii_line_10_cents == disposals["form_4797_part_ii_line_10_cents"]


def test_the_depreciation_column_is_what_the_disposal_entry_posted(
    settings: Settings,
) -> None:
    """Finding 3 from the blind judge. The schedule said 130.00 where the journal said 65.00.

    The laptop cost 1,800.00 and the books still carried 850.00 on the day it left, so the
    disposal entry debited 950.00 of accumulated depreciation. This column reads that figure
    and no other.
    """
    with session_scope() as session:
        build_disposals(session)
        block = form4797.compute(session, PERIOD_START, PERIOD_END)
        records = {
            row.label: row for row in session.scalars(select(models.ItemRecord))
        }

    row = next(r for r in block.part_ii_rows if r.description == "laptop")
    assert row.depreciation_allowed_cents == 95_000
    assert row.cost_cents - records["laptop"].book_value_cents == 95_000

    keyboard = next(r for r in block.part_ii_rows if r.description == "mechanical keyboard")
    assert keyboard.depreciation_allowed_cents == 10_000
