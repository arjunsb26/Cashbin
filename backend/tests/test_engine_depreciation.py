from __future__ import annotations

from datetime import date

from app.engine.depreciation import book_value, months_between, tax_basis
from app.engine.records import AssetInfo, TaxMethod


def asset(**overrides: object) -> AssetInfo:
    base = {
        "id": 1,
        "tag": "BB-0001",
        "description": "Test asset",
        "cost_cents": 120000,
        "in_service_date": date(2024, 1, 15),
        "book_life_months": 48,
        "salvage_cents": 0,
        "tax_method": TaxMethod.straight_line,
    }
    base.update(overrides)
    return AssetInfo(**base)


def test_months_between_counts_whole_months_only() -> None:
    start = date(2025, 1, 31)
    assert months_between(start, date(2025, 1, 31)) == 0
    assert months_between(start, date(2025, 2, 28)) == 0
    assert months_between(start, date(2025, 3, 31)) == 2


def test_months_between_turns_over_on_the_anniversary_day() -> None:
    start = date(2025, 3, 15)
    assert months_between(start, date(2025, 4, 14)) == 0
    assert months_between(start, date(2025, 4, 15)) == 1
    assert months_between(start, date(2025, 4, 16)) == 1


def test_months_between_is_never_negative() -> None:
    assert months_between(date(2026, 1, 1), date(2025, 1, 1)) == 0


def test_mid_life_book_value() -> None:
    value = book_value(asset(), date(2026, 1, 15))
    assert value.months_used == 24
    assert value.accum_cents == 60000
    assert value.book_value_cents == 60000


def test_fully_depreciated_stops_at_the_end_of_life() -> None:
    value = book_value(asset(), date(2040, 1, 1))
    assert value.months_used == 48
    assert value.accum_cents == 120000
    assert value.book_value_cents == 0


def test_salvage_is_never_depreciated_away() -> None:
    value = book_value(asset(salvage_cents=20000), date(2040, 1, 1))
    assert value.accum_cents == 100000
    assert value.book_value_cents == 20000


def test_bonus_100_leaves_no_tax_basis() -> None:
    item = asset(tax_method=TaxMethod.bonus_100)
    assert book_value(item, date(2026, 1, 15)).book_value_cents == 60000
    assert tax_basis(item, date(2026, 1, 15)) == 0


def test_straight_line_tax_basis_equals_book_value() -> None:
    item = asset()
    on = date(2026, 1, 15)
    assert tax_basis(item, on) == book_value(item, on).book_value_cents


def test_override_wins_over_the_method() -> None:
    item = asset(tax_method=TaxMethod.bonus_100, tax_basis_cents_override=4500)
    assert tax_basis(item, date(2026, 1, 15)) == 4500


def test_asset_with_no_cost_yet_reports_zero_rather_than_guessing() -> None:
    item = asset(cost_cents=None)
    value = book_value(item, date(2026, 1, 15))
    assert value.book_value_cents == 0
    assert value.accum_cents == 0


def test_asset_with_no_life_on_file_still_stands_at_cost() -> None:
    item = asset(book_life_months=None)
    assert book_value(item, date(2026, 1, 15)).book_value_cents == 120000
