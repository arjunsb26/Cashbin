from __future__ import annotations

from datetime import date

from app.engine.records import (
    AssetInfo,
    AssetStatus,
    CatalogItem,
    Condition,
    EngineSettings,
    Estimate,
    EstimateSource,
    ItemClass,
    TaxMethod,
    as_row,
    build_item_record,
    catalog_by_label,
)

EVENT_DATE = date(2026, 9, 19)


def test_default_settings_match_the_plan() -> None:
    settings = EngineSettings()
    assert settings.tax_rate == 0.21
    assert settings.disposal_fee_cents == 0
    assert settings.recycle_fee_cents == 0
    assert settings.capitalization_threshold_cents == 50000
    assert settings.tie_break_cents == 50


def test_cost_basis_from_a_price_per_kilo() -> None:
    item = CatalogItem(
        id=1,
        label="banana",
        item_class=ItemClass.inventory,
        price_per_kg_cents=143,
        material_mix={"food_waste": 1.0},
    )
    record = build_item_record(
        event_id=1,
        label="banana",
        item_class=ItemClass.inventory,
        mass_g=236.0,
        event_date=EVENT_DATE,
        catalog=item,
    )
    assert record.cost_basis_cents == 34


def test_cost_basis_scales_with_the_fraction_of_a_unit_that_was_tossed() -> None:
    item = catalog_by_label()["bagel"]
    half = build_item_record(
        event_id=1,
        label="bagel",
        item_class=ItemClass.inventory,
        mass_g=47.5,
        event_date=EVENT_DATE,
        catalog=item,
    )
    assert half.cost_basis_cents == 16


def test_a_catalog_row_with_no_price_leaves_the_cost_basis_empty() -> None:
    item = CatalogItem(
        id=1,
        label="mystery",
        item_class=ItemClass.inventory,
        material_mix={"mixed_plastics": 1.0},
    )
    record = build_item_record(
        event_id=1,
        label="mystery",
        item_class=ItemClass.inventory,
        mass_g=100.0,
        event_date=EVENT_DATE,
        catalog=item,
    )
    assert record.cost_basis_cents is None


def test_the_material_mix_and_flags_come_from_the_catalog_when_not_given() -> None:
    record = build_item_record(
        event_id=1,
        label="phone",
        item_class=ItemClass.untracked,
        mass_g=200.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["phone"],
    )
    assert record.material_mix == {"portable_electronic_devices": 1.0}
    assert record.regulatory_flags == ["electronics", "battery"]


def test_an_estimate_from_a_model_beats_the_catalog_value() -> None:
    record = build_item_record(
        event_id=1,
        label="bagel",
        item_class=ItemClass.inventory,
        mass_g=95.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["bagel"],
        fmv=Estimate(low=100, mid=150, high=200, source=EstimateSource.human),
    )
    assert record.fmv_mid == 150
    assert record.fmv_source is EstimateSource.human
    assert record.fmv is not None
    assert record.fmv.low == 100


def test_a_fixed_asset_takes_its_values_from_the_register() -> None:
    asset = AssetInfo(
        id=5,
        tag="BB-0005",
        description="Webcam",
        cost_cents=6000,
        in_service_date=date(2025, 9, 19),
        book_life_months=36,
        tax_method=TaxMethod.straight_line,
        status=AssetStatus.active,
    )
    record = build_item_record(
        event_id=1,
        label="webcam",
        item_class=ItemClass.fixed_asset,
        mass_g=160.0,
        event_date=EVENT_DATE,
        asset=asset,
        condition=Condition.broken,
    )
    assert record.book_value_cents == 4000
    assert record.tax_basis_cents == 4000
    assert record.asset_id == 5
    assert record.condition is Condition.broken


def test_an_untracked_item_carries_no_book_value() -> None:
    record = build_item_record(
        event_id=1,
        label="usb cable",
        item_class=ItemClass.untracked,
        mass_g=40.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["usb cable"],
    )
    assert record.book_value_cents == 0
    assert record.tax_basis_cents == 0
    assert record.cost_basis_cents is None


def test_mass_in_kilograms_is_the_grams_divided_by_a_thousand() -> None:
    record = build_item_record(
        event_id=1,
        label="pizza box",
        item_class=ItemClass.inventory,
        mass_g=300.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["pizza box"],
    )
    assert record.mass_kg == 0.3


def test_the_record_serialises_under_the_database_column_names() -> None:
    row = as_row(
        build_item_record(
            event_id=1,
            label="bagel",
            item_class=ItemClass.inventory,
            mass_g=95.0,
            event_date=EVENT_DATE,
            catalog=catalog_by_label()["bagel"],
        )
    )
    assert row["class"] == "inventory"
    assert "item_class" not in row
    assert row["event_date"] == "2026-09-19"
