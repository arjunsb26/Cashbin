"""Fixed asset register operations, as pure functions on `AssetInfo` lists.

Nothing here writes. Each function hands back a new object or a summary, and
the caller decides what to save.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.engine import depreciation
from app.engine.records import AssetInfo, AssetStatus


class BookSummary(BaseModel):
    """What the register is worth on a given day."""

    model_config = ConfigDict(frozen=True)

    on: date
    active_count: int
    disposed_count: int
    ghost_suspected_count: int
    cost_cents: int
    accum_cents: int
    book_value_cents: int
    tax_basis_cents: int
    assets_missing_cost: tuple[str, ...] = ()


def mark_disposed(asset: AssetInfo, event_id: int) -> AssetInfo:
    """Take the asset off the register, pointing at the toss that did it."""
    return asset.model_copy(
        update={
            "status": AssetStatus.disposed,
            "disposed_event_id": event_id,
        }
    )


def mark_ghost_suspected(asset: AssetInfo) -> AssetInfo:
    return asset.model_copy(update={"status": AssetStatus.ghost_suspected})


def find_ghosts(
    assets: Iterable[AssetInfo],
    disposed_event_asset_ids: Iterable[int],
) -> list[AssetInfo]:
    """Assets an event threw away that the register still shows as in use.

    The close reports these. They are the register disagreeing with the bin,
    and the bin is the one with physical evidence.
    """
    disposed = set(disposed_event_asset_ids)
    return [
        asset
        for asset in assets
        if asset.id in disposed and asset.status is AssetStatus.active
    ]


def book_summary(assets: Iterable[AssetInfo], on: date) -> BookSummary:
    """Totals across the register, counting only assets still in use."""
    items = list(assets)
    cost = accum = book = basis = 0
    missing: list[str] = []
    active = disposed = ghosts = 0

    for asset in items:
        if asset.status is AssetStatus.disposed:
            disposed += 1
            continue
        if asset.status is AssetStatus.ghost_suspected:
            ghosts += 1
        else:
            active += 1
        if asset.cost_cents is None:
            missing.append(asset.tag)
            continue
        value = depreciation.book_value(asset, on)
        cost += asset.cost_cents
        accum += value.accum_cents
        book += value.book_value_cents
        basis += depreciation.tax_basis(asset, on)

    return BookSummary(
        on=on,
        active_count=active,
        disposed_count=disposed,
        ghost_suspected_count=ghosts,
        cost_cents=cost,
        accum_cents=accum,
        book_value_cents=book,
        tax_basis_cents=basis,
        assets_missing_cost=tuple(missing),
    )


def by_tag(assets: Iterable[AssetInfo]) -> dict[str, AssetInfo]:
    """Tag to asset, which is how a scanned QR code finds its row."""
    return {asset.tag: asset for asset in assets}
