"""Book value and tax basis for a fixed asset, per PLAN.md section 10.

Straight line for the books. For tax, `bonus_100` means the asset was fully
expensed in its first year, so nothing is left to deduct. An explicit override
on the asset wins over both.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.engine.records import AssetInfo, TaxMethod


class BookValue(BaseModel):
    """What the books say an asset is worth on a given day."""

    model_config = ConfigDict(frozen=True)

    months_used: int
    accum_cents: int
    book_value_cents: int


def months_between(start: date, end: date) -> int:
    """Whole months from `start` to `end`, never negative.

    The month only counts once the day of the month comes round again, so an
    asset put in service on the 15th has used one month on the 15th of the next
    month and not a day before.
    """
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def book_value(asset: AssetInfo, on: date) -> BookValue:
    """Straight line depreciation down to salvage, stopping at the end of life."""
    cost = asset.cost_cents
    if cost is None:
        return BookValue(months_used=0, accum_cents=0, book_value_cents=0)

    life = asset.book_life_months
    salvage = min(asset.salvage_cents, cost)
    depreciable = max(cost - salvage, 0)

    if asset.in_service_date is None or not life:
        # Nothing to depreciate over, so the asset still stands at cost.
        return BookValue(months_used=0, accum_cents=0, book_value_cents=cost)

    months_used = min(months_between(asset.in_service_date, on), life)
    accum = round(depreciable * months_used / life)
    return BookValue(
        months_used=months_used,
        accum_cents=accum,
        book_value_cents=cost - accum,
    )


def tax_basis(asset: AssetInfo, on: date) -> int:
    """What is left to deduct for tax on a given day."""
    if asset.tax_basis_cents_override is not None:
        return asset.tax_basis_cents_override
    if asset.tax_method is TaxMethod.bonus_100:
        return 0
    if asset.tax_method is TaxMethod.straight_line:
        return book_value(asset, on).book_value_cents
    # No method on file yet. Treat the basis as the book value and let the
    # setup checklist chase the missing cell.
    return book_value(asset, on).book_value_cents
