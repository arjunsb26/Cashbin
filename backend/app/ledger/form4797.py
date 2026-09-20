"""The Form 4797 schedule: what left the register, laid out the way the form is.

PLAN.md 21a item 39. This is plain data. It is not a filing, it is not advice,
and nothing here claims either: it is the same disposals the close already
reports, arranged in the two places that form puts them.

- Part II, line 10 takes abandonments: business property thrown away with nothing
  received for it. What is left of the tax basis is an ordinary loss, so the
  subtotal is negative when the period lost money, which is how that line reads.
- Part III takes sales. When an asset sells for more than its tax basis, the part
  of the gain that matches depreciation already taken is ordinary income rather
  than capital gain, which the row notes.

The rule ids on every row come from `tax_rules.yaml` and nowhere else, so the
evidence drawer can show the words behind each one without a second copy.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ledger.reconciliation import _day, _event_day, _proceeds
from app.schemas import Form4797Block, Form4797Row

# The one copy of the footer every finance view carries, per PLAN.md section 10.
DISCLAIMER = "Estimates for review. Not tax advice."

PART_II_LINE = "Part II, line 10 (abandonments)"
PART_III_LINE = "Part III (gain from disposition of depreciable property)"

RECAPTURE_NOTE = (
    "The part of this gain that matches depreciation already taken is taxed as "
    "ordinary income."
)


def _rows_in_period(
    session: Session, start: date, end: date
) -> list[tuple[models.Event, models.ItemRecord, models.Asset | None]]:
    out: list[tuple[models.Event, models.ItemRecord, models.Asset | None]] = []
    for event in session.scalars(select(models.Event).order_by(models.Event.id)):
        if event.kind is not models.EventKind.toss:
            continue
        if event.status is models.EventStatus.void:
            continue
        if not (start <= _event_day(event) <= end):
            continue
        record = session.get(models.ItemRecord, event.id)
        if record is None or record.item_class is not models.ItemClass.fixed_asset:
            continue
        asset = session.get(models.Asset, record.asset_id) if record.asset_id else None
        out.append((event, record, asset))
    return out


def _row(
    event: models.Event,
    record: models.ItemRecord,
    asset: models.Asset | None,
    proceeds: int,
) -> Form4797Row:
    cost = asset.cost_cents if asset is not None else 0
    basis = record.tax_basis_cents
    # The accumulated depreciation the disposal entry took off the register, which is the
    # asset's cost less what the books still carried on the day it left. Reading it off the
    # same figure the journal posted is the point: this column used to be cost less tax
    # basis, so a bonus asset counted its first year write off here as well as in the tax
    # basis, and the schedule said 130.00 where the journal and the disposal table said
    # 65.00 about one keyboard. The gain or loss below stays on the tax basis, so the
    # Part II subtotal is still the figure the close reports.
    depreciation_allowed = max(cost - record.book_value_cents, 0)
    gain_or_loss = proceeds - basis
    abandoned = proceeds == 0

    rule_ids = ["ABANDON"] if abandoned else ["RECAPTURE"]
    if asset is not None and asset.tax_method is models.TaxMethod.bonus_100:
        rule_ids.append("BONUS_100")

    return Form4797Row(
        description=asset.description if asset is not None else record.label,
        date_acquired=(asset.in_service_date or "")[:10] if asset is not None else "",
        date_disposed=_event_day(event).isoformat(),
        gross_proceeds_cents=proceeds,
        cost_cents=cost,
        depreciation_allowed_cents=depreciation_allowed,
        gain_or_loss_cents=gain_or_loss,
        part="II" if abandoned else "III",
        line=PART_II_LINE if abandoned else PART_III_LINE,
        rule_ids=rule_ids,
        recapture_note="" if abandoned else RECAPTURE_NOTE,
    )


def compute(session: Session, period_start: str, period_end: str) -> Form4797Block:
    """Every disposal in the period, in its part of the form, with both subtotals."""
    start = _day(period_start, date.min)
    end = _day(period_end, date.max)

    part_ii: list[Form4797Row] = []
    part_iii: list[Form4797Row] = []
    for event, record, asset in _rows_in_period(session, start, end):
        row = _row(event, record, asset, _proceeds(session, event.id))
        (part_ii if row.part == "II" else part_iii).append(row)

    part_ii.sort(key=lambda row: (row.gain_or_loss_cents, row.description))
    part_iii.sort(key=lambda row: (-row.gain_or_loss_cents, row.description))

    return Form4797Block(
        part_ii_rows=part_ii,
        part_iii_rows=part_iii,
        part_ii_line_10_cents=sum(row.gain_or_loss_cents for row in part_ii),
        part_iii_recapture_cents=sum(
            max(row.gain_or_loss_cents, 0) for row in part_iii
        ),
        disclaimer=DISCLAIMER,
    )
