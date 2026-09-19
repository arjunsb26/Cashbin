"""The three demo items, built once and shared by the other engine tests.

PLAN.md section 20 names these as the M3 acceptance check: a tagged keyboard
that shows a book loss against a zero tax basis, a bagel where donating beats
binning, and a charger that may not go in the landfill at all.
"""

from __future__ import annotations

from datetime import date

from app.engine.records import (
    AssetInfo,
    AssetStatus,
    Condition,
    EngineSettings,
    Estimate,
    EstimateSource,
    ItemClass,
    ItemRecord,
    TaxMethod,
    build_item_record,
    catalog_by_label,
)

EVENT_DATE = date(2026, 9, 19)
SETTINGS = EngineSettings()

KEYBOARD_ASSET = AssetInfo(
    id=2,
    tag="BB-0002",
    description="Mechanical keyboard",
    category="peripheral",
    cost_cents=12000,
    in_service_date=date(2025, 3, 15),
    book_life_months=36,
    salvage_cents=0,
    tax_method=TaxMethod.bonus_100,
    status=AssetStatus.active,
    location="hack table",
)


def keyboard_record() -> ItemRecord:
    """A tagged asset, eighteen months into a three year life."""
    return build_item_record(
        event_id=1,
        label="keyboard",
        item_class=ItemClass.fixed_asset,
        mass_g=685.0,
        event_date=EVENT_DATE,
        asset=KEYBOARD_ASSET,
        condition=Condition.broken,
        material_mix={"electronic_peripherals": 1.0},
        regulatory_flags=["electronics"],
        fmv=Estimate(low=1500, mid=2000, high=3000, source=EstimateSource.model_estimate),
        repair=Estimate(low=1000, mid=1500, high=2500, source=EstimateSource.model_estimate),
        replacement_cents=12000,
        replacement_source=EstimateSource.model_estimate,
    )


def bagel_record() -> ItemRecord:
    """A catalog food item at its catalog mass."""
    return build_item_record(
        event_id=2,
        label="bagel",
        item_class=ItemClass.inventory,
        mass_g=95.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["bagel"],
    )


def charger_record() -> ItemRecord:
    """Small electronics nobody put on the register."""
    return build_item_record(
        event_id=3,
        label="usb-c charger",
        item_class=ItemClass.untracked,
        mass_g=31.0,
        event_date=EVENT_DATE,
        catalog=catalog_by_label()["usb-c charger"],
    )


def test_keyboard_record_has_book_value_and_zero_tax_basis() -> None:
    record = keyboard_record()
    assert record.book_value_cents == 6000
    assert record.tax_basis_cents == 0
    assert record.asset_id == 2


def test_bagel_record_takes_cost_and_value_from_the_catalog() -> None:
    record = bagel_record()
    assert record.cost_basis_cents == 66
    assert record.fmv_mid == 66
    assert record.fmv_source is EstimateSource.catalog
    assert record.material_mix == {"food_waste": 1.0}


def test_charger_record_carries_the_electronics_flag() -> None:
    record = charger_record()
    assert record.regulatory_flags == ["electronics"]
    assert record.material_mix == {"mixed_electronics": 1.0}
    assert record.cost_basis_cents is None
