"""The fixed asset rollforward: what the register held, what moved, what is left.

PLAN.md 21a item 39. This is the schedule an auditor asks for first, because it
is the one that has to tie: closing equals opening plus what came in less what
went out, on cost and on accumulated depreciation, per asset and in total.

Every figure is read off the register and off `depreciation.py`. Nothing here has
its own idea of straight line, so a change to the depreciation rule lands in this
schedule on the same commit.

The conventions, written down because every rollforward has them and an unwritten
one is an argument waiting to happen:

- Opening is the position as of the first day of the period, closing as of the
  last. Depreciation for the period is the difference between the two.
- An asset stops depreciating on the day it leaves, so its disposal takes out the
  accumulated depreciation it had reached on that day and not a month more.
- An asset that left before this period never appears in these movements.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.engine import depreciation
from app.engine.records import AssetInfo
from app.schemas import RollforwardBlock, RollforwardRow


def _day(text: str, fallback: date) -> date:
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return fallback


def _event_day(row: models.Event | None) -> date | None:
    if row is None:
        return None
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return None
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).date()


def _accum(info: AssetInfo, on: date) -> int:
    return depreciation.book_value(info, on).accum_cents


def row_for(
    asset: models.Asset,
    info: AssetInfo,
    start: date,
    end: date,
    disposed_on: date | None,
) -> RollforwardRow:
    """One asset's movement through the period.

    The four cases are held, added, disposed, and already gone, and they are the
    only four there are.
    """
    cost = asset.cost_cents
    in_service = info.in_service_date or start
    gone_before = disposed_on is not None and disposed_on < start
    left_here = disposed_on is not None and start <= disposed_on <= end
    added_here = start <= in_service <= end

    on_books_at_start = in_service < start and not gone_before
    opening_cost = cost if on_books_at_start else 0
    additions = cost if added_here and not gone_before else 0
    disposals_cost = cost if left_here else 0

    opening_accum = _accum(info, start) if on_books_at_start else 0
    if gone_before:
        closing_accum = 0
        depreciation_cents = 0
        disposals_accum = 0
    elif left_here:
        assert disposed_on is not None
        disposals_accum = _accum(info, disposed_on)
        depreciation_cents = disposals_accum - opening_accum
        closing_accum = 0
    else:
        closing_accum = _accum(info, end)
        depreciation_cents = closing_accum - opening_accum
        disposals_accum = 0

    closing_cost = opening_cost + additions - disposals_cost
    return RollforwardRow(
        asset_id=asset.id,
        tag=asset.tag,
        description=asset.description,
        opening_cost_cents=opening_cost,
        additions_cents=additions,
        disposals_cost_cents=disposals_cost,
        closing_cost_cents=closing_cost,
        opening_accum_cents=opening_accum,
        depreciation_cents=depreciation_cents,
        disposals_accum_cents=disposals_accum,
        closing_accum_cents=closing_accum,
        opening_nbv_cents=opening_cost - opening_accum,
        closing_nbv_cents=closing_cost - closing_accum,
    )


_MOVEMENT_FIELDS: tuple[str, ...] = (
    "opening_cost_cents",
    "additions_cents",
    "disposals_cost_cents",
    "closing_cost_cents",
    "opening_accum_cents",
    "depreciation_cents",
    "disposals_accum_cents",
    "closing_accum_cents",
    "opening_nbv_cents",
    "closing_nbv_cents",
)


def total_of(rows: list[RollforwardRow]) -> RollforwardRow:
    """The bottom line, added column by column."""
    totals = {
        field: sum(getattr(row, field) for row in rows) for field in _MOVEMENT_FIELDS
    }
    return RollforwardRow(tag="", description="Total", **totals)


def ties(row: RollforwardRow) -> bool:
    """Opening plus movements equals closing, on both halves of the schedule."""
    return (
        row.closing_cost_cents
        == row.opening_cost_cents + row.additions_cents - row.disposals_cost_cents
        and row.closing_accum_cents
        == row.opening_accum_cents + row.depreciation_cents - row.disposals_accum_cents
    )


def compute(session: Session, period_start: str, period_end: str) -> RollforwardBlock:
    """The whole schedule for one period, largest closing cost first."""
    start = _day(period_start, date.min)
    end = _day(period_end, date.max)

    # Imported here rather than at the top: the close imports this module, and the
    # row conversion lives over there.
    from app.ledger.close import to_asset_info

    assets = list(session.scalars(select(models.Asset).order_by(models.Asset.id)))
    event_ids = [row.disposed_event_id for row in assets if row.disposed_event_id]
    events: dict[int, models.Event] = {}
    if event_ids:
        for row in session.scalars(
            select(models.Event).where(models.Event.id.in_(event_ids))
        ):
            events[row.id] = row

    rows: list[RollforwardRow] = []
    for asset in assets:
        disposed_on = _event_day(
            events.get(asset.disposed_event_id) if asset.disposed_event_id else None
        )
        rows.append(row_for(asset, to_asset_info(asset), start, end, disposed_on))

    rows.sort(key=lambda row: (-row.closing_cost_cents, row.tag))
    total = total_of(rows)
    return RollforwardBlock(
        period_start=period_start,
        period_end=period_end,
        rows=rows,
        total=total,
        ties=all(ties(row) for row in [*rows, total]),
    )
