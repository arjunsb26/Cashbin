from __future__ import annotations

from datetime import date

from app.engine.records import AssetInfo, AssetStatus, TaxMethod
from app.ledger.register import (
    book_summary,
    by_tag,
    find_ghosts,
    mark_disposed,
    mark_ghost_suspected,
)

ON = date(2026, 9, 19)


def asset(asset_id: int, **overrides: object) -> AssetInfo:
    base = {
        "id": asset_id,
        "tag": f"BB-{asset_id:04d}",
        "description": f"Asset {asset_id}",
        "cost_cents": 120000,
        "in_service_date": date(2025, 9, 19),
        "book_life_months": 48,
        "tax_method": TaxMethod.straight_line,
    }
    base.update(overrides)
    return AssetInfo(**base)


def test_mark_disposed_points_at_the_toss_that_did_it() -> None:
    updated = mark_disposed(asset(1), event_id=42)
    assert updated.status is AssetStatus.disposed
    assert updated.disposed_event_id == 42


def test_mark_disposed_leaves_the_original_alone() -> None:
    original = asset(1)
    mark_disposed(original, event_id=42)
    assert original.status is AssetStatus.active
    assert original.disposed_event_id is None


def test_ghosts_are_assets_the_bin_saw_but_the_register_still_lists() -> None:
    assets = [
        asset(1),
        asset(2),
        mark_disposed(asset(3), event_id=7),
    ]
    ghosts = find_ghosts(assets, [2, 3])
    assert [item.id for item in ghosts] == [2]


def test_no_ghosts_when_the_register_agrees_with_the_bin() -> None:
    assets = [asset(1), mark_disposed(asset(2), event_id=9)]
    assert find_ghosts(assets, [2]) == []


def test_book_summary_totals_the_assets_still_in_use() -> None:
    assets = [asset(1), asset(2), mark_disposed(asset(3), event_id=5)]
    summary = book_summary(assets, ON)
    assert summary.active_count == 2
    assert summary.disposed_count == 1
    assert summary.cost_cents == 240000
    # One year of a four year life on each.
    assert summary.accum_cents == 60000
    assert summary.book_value_cents == 180000
    assert summary.tax_basis_cents == 180000


def test_book_summary_reports_a_bonus_asset_at_zero_tax_basis() -> None:
    summary = book_summary([asset(1, tax_method=TaxMethod.bonus_100)], ON)
    assert summary.book_value_cents == 90000
    assert summary.tax_basis_cents == 0


def test_book_summary_names_assets_with_no_cost_on_file() -> None:
    summary = book_summary([asset(1, cost_cents=None), asset(2)], ON)
    assert summary.assets_missing_cost == ("BB-0001",)
    assert summary.cost_cents == 120000


def test_book_summary_counts_ghost_suspects_separately() -> None:
    summary = book_summary([mark_ghost_suspected(asset(1)), asset(2)], ON)
    assert summary.ghost_suspected_count == 1
    assert summary.active_count == 1


def test_book_summary_of_an_empty_register_is_all_zero() -> None:
    summary = book_summary([], ON)
    assert summary.active_count == 0
    assert summary.cost_cents == 0
    assert summary.book_value_cents == 0


def test_by_tag_is_how_a_scanned_code_finds_its_row() -> None:
    table = by_tag([asset(1), asset(2)])
    assert table["BB-0002"].id == 2
