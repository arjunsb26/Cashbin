"""Book to tax on disposals, in the shape Schedule M-1 asks for.

PLAN.md 21a item 39. The books and the tax return disagree about a disposal
whenever the asset's tax basis is not its book value, which is nearly always the
case once something has been expensed in full in its first year. This schedule
says how much they disagree by, and why, one asset at a time.

The bridge is the point of it:

    book loss on disposals, less the differences, equals the tax loss on disposals

If that does not close, the schedule is wrong, so the block carries whether it
closed rather than leaving anyone to add it up by hand.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.schemas import ReconciliationBlock, ReconciliationRow

TITLE = "Book to tax, losses on disposals (Schedule M-1 shape)"

REASON_OVERRIDE = "override"
REASON_STRAIGHT_LINE = "straight line, no difference"


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _day(text: str, fallback: date) -> date:
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return fallback


def _event_day(row: models.Event) -> date:
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return date.min
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).date()


def reason_for(asset: models.Asset | None, difference_cents: int) -> str:
    """Why book and tax differ on this asset, in the words a CFO would use.

    An override wins, because somebody typed it and that is the whole story.
    Otherwise the method explains it: full first year expensing leaves nothing to
    deduct on the way out, and straight line leaves book and tax equal.
    """
    if asset is None:
        return "no register row for this disposal" if difference_cents else REASON_STRAIGHT_LINE
    if asset.tax_basis_cents_override is not None:
        return REASON_OVERRIDE
    if asset.tax_method is models.TaxMethod.bonus_100:
        year = (asset.in_service_date or "")[:4] or "an earlier year"
        return f"bonus_100 taken in {year}"
    return REASON_STRAIGHT_LINE


def rule_ids_for(asset: models.Asset | None) -> list[str]:
    """The rule ids behind the difference, all of them in `tax_rules.yaml`."""
    ids = ["ABANDON"]
    if asset is not None and asset.tax_method is models.TaxMethod.bonus_100:
        ids.append("BONUS_100")
    return ids


def _proceeds(session: Session, event_id: int) -> int:
    """What came in for this disposal, off the entry that posted it."""
    for row in session.scalars(
        select(models.JournalEntry)
        .where(models.JournalEntry.event_id == event_id)
        .order_by(models.JournalEntry.id)
    ):
        if row.basis is not models.JournalBasis.book:
            continue
        evidence = _loads(row.evidence_json, {})
        if isinstance(evidence, dict) and "gain_cents" in evidence:
            return int(evidence.get("proceeds_cents") or 0)
    return 0


def compute(session: Session, period_start: str, period_end: str) -> ReconciliationBlock:
    """Every asset disposal in the period, book against tax, with the bridge."""
    start = _day(period_start, date.min)
    end = _day(period_end, date.max)

    events = [
        row
        for row in session.scalars(select(models.Event).order_by(models.Event.id))
        if row.kind is models.EventKind.toss
        and row.status is not models.EventStatus.void
        and start <= _event_day(row) <= end
    ]
    rows: list[ReconciliationRow] = []
    for event in events:
        record = session.get(models.ItemRecord, event.id)
        if record is None or record.item_class is not models.ItemClass.fixed_asset:
            continue
        asset = session.get(models.Asset, record.asset_id) if record.asset_id else None
        proceeds = _proceeds(session, event.id)
        book_loss = max(record.book_value_cents - proceeds, 0)
        tax_loss = max(record.tax_basis_cents - proceeds, 0)
        difference = book_loss - tax_loss
        rows.append(
            ReconciliationRow(
                event_id=event.id,
                asset_id=record.asset_id,
                tag=asset.tag if asset else "",
                description=asset.description if asset else record.label,
                book_loss_cents=book_loss,
                tax_loss_cents=tax_loss,
                difference_cents=difference,
                reason=reason_for(asset, difference),
                rule_ids=rule_ids_for(asset),
            )
        )

    rows.sort(key=lambda row: (-row.difference_cents, row.event_id))
    book_total = sum(row.book_loss_cents for row in rows)
    tax_total = sum(row.tax_loss_cents for row in rows)
    difference_total = sum(row.difference_cents for row in rows)
    return ReconciliationBlock(
        rows=rows,
        book_loss_cents=book_total,
        differences_cents=difference_total,
        tax_loss_cents=tax_total,
        ties=book_total - difference_total == tax_total,
        title=TITLE,
    )
