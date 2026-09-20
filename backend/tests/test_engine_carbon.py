from __future__ import annotations

from datetime import date

from app.engine import carbon
from app.engine.carbon import Fate
from app.engine.records import ItemClass, ItemRecord, Option

EVENT_DATE = date(2026, 9, 19)


def record(mix: dict[str, float], mass_g: float = 1000.0) -> ItemRecord:
    return ItemRecord(
        event_id=1,
        label="thing",
        item_class=ItemClass.inventory,
        mass_g=mass_g,
        event_date=EVENT_DATE,
        material_mix=mix,
    )


def test_unit_conversion_from_mtco2e_per_short_ton() -> None:
    """One metric ton of CO2e per short ton is 1000 kg spread over 907.18474 kg."""
    assert carbon.mtco2e_per_short_ton_to_kg_per_kg(1.0) == 1000.0 / 907.18474
    assert round(carbon.mtco2e_per_short_ton_to_kg_per_kg(1.0), 6) == 1.102311
    assert carbon.mtco2e_per_short_ton_to_kg_per_kg(0.0) == 0.0
    assert carbon.mtco2e_per_short_ton_to_kg_per_kg(-2.0) == -2000.0 / 907.18474


def test_the_table_carries_the_workbook_numbers_converted() -> None:
    # Food waste to landfill reads 0.5014622340279833 MTCO2E per short ton.
    value = carbon.factor("food_waste", Fate.landfill)
    assert value is not None
    assert round(value, 6) == round(0.5014622340279833 * 1000 / 907.18474, 6)


def test_the_materials_the_catalog_needs_are_all_present() -> None:
    for material in (
        "food_waste",
        "mixed_paper",
        "corrugated_containers",
        "mixed_plastics",
        "pet",
        "aluminum_cans",
        "steel_cans",
        "glass",
        "mixed_electronics",
    ):
        assert material in carbon.known_materials()


def test_an_unknown_material_returns_none_not_zero() -> None:
    assert carbon.factor("unobtainium", Fate.landfill) is None
    item = record({"unobtainium": 1.0})
    result = carbon.carbon_for(item, Option.trash)
    assert result.kg_co2e is None
    assert result.missing_materials == ("unobtainium",)


def test_a_material_with_no_factor_for_that_fate_returns_none() -> None:
    # WARM publishes no recycling factor for food waste.
    assert carbon.factor("food_waste", Fate.recycle) is None


def test_an_empty_material_mix_is_unknown_rather_than_zero() -> None:
    result = carbon.carbon_for(record({}), Option.trash)
    assert result.kg_co2e is None
    assert result.missing_materials == ("unknown material",)


def test_mix_fractions_weight_correctly() -> None:
    paper = carbon.factor("mixed_paper", Fate.landfill)
    plastic = carbon.factor("mixed_plastics", Fate.landfill)
    assert paper is not None and plastic is not None
    item = record({"mixed_paper": 0.75, "mixed_plastics": 0.25}, mass_g=2000.0)
    result = carbon.carbon_for(item, Option.trash)
    assert result.kg_co2e is not None
    expected = 2.0 * (0.75 * paper + 0.25 * plastic)
    assert round(result.kg_co2e, 9) == round(expected, 9)


def test_food_recycling_uses_the_compost_column() -> None:
    item = record({"food_waste": 1.0})
    result = carbon.carbon_for(item, Option.recycle)
    assert result.fate is Fate.compost
    compost = carbon.factor("food_waste", Fate.compost)
    assert compost is not None
    assert result.kg_co2e is not None
    assert round(result.kg_co2e, 9) == round(compost, 9)


def test_non_food_recycling_uses_the_recycling_column() -> None:
    item = record({"pet": 1.0})
    result = carbon.carbon_for(item, Option.recycle)
    assert result.fate is Fate.recycle


def test_resell_donate_and_repair_all_count_as_source_reduction() -> None:
    item = record({"mixed_electronics": 1.0})
    for option in (Option.resell, Option.donate, Option.repair):
        assert carbon.carbon_for(item, option).fate is Fate.source_reduction


def test_landfill_mass_is_the_whole_item_for_trash_and_nothing_otherwise() -> None:
    item = record({"mixed_paper": 1.0}, mass_g=250.0)
    assert carbon.kg_landfill(item, Option.trash) == 0.25
    for option in (Option.recycle, Option.resell, Option.donate, Option.repair):
        assert carbon.kg_landfill(item, option) == 0.0


def test_a_mostly_food_mix_counts_as_food() -> None:
    assert carbon.is_food(record({"food_waste": 0.86, "mixed_plastics": 0.14}))
    assert not carbon.is_food(record({"food_waste": 0.2, "mixed_plastics": 0.8}))


def test_binning_food_warms_the_planet_and_composting_it_does_not() -> None:
    item = record({"food_waste": 1.0})
    trash = carbon.kg_co2e(item, Option.trash)
    compost = carbon.kg_co2e(item, Option.recycle)
    assert trash is not None and compost is not None
    assert trash > 0 > compost


# Every catalog item has a carbon answer for every option -----------------------


def test_every_catalog_material_is_in_the_warm_table() -> None:
    """A key the table does not have is a ticket with no carbon on it."""
    from app.engine.records import load_catalog

    used = {material for item in load_catalog() for material in item.material_mix}
    missing = sorted(used - carbon.known_materials())
    assert not missing, f"not in warm_factors.csv: {missing}"


def test_every_catalog_item_gets_a_number_for_every_option() -> None:
    """The real run showed "unknown" on two tickets. This is the invariant that catches it."""
    from datetime import date

    from app.engine.records import ItemRecord, load_catalog

    blank: list[str] = []
    for item in load_catalog():
        if not item.material_mix:
            blank.append(item.label)
            continue
        record = ItemRecord.model_validate(
            {
                "event_id": 1,
                "label": item.label,
                "class": str(item.item_class),
                "mass_g": item.unit_mass_g or item.mass_prior_mean_g or 100.0,
                "event_date": date(2026, 9, 19),
                "material_mix": dict(item.material_mix),
            }
        )
        for option in Option:
            result = carbon.carbon_for(record, option)
            assert result.kg_co2e is not None, (
                f"{item.label} has no carbon for {option.value}: {result.missing_materials}"
            )
    assert not blank, f"catalog rows with no material mix: {blank}"


def test_the_estimator_may_only_name_materials_warm_publishes() -> None:
    """A model that invents a material key produces a ticket with no carbon on it."""
    from app.identify.openai_request import MATERIAL_VOCABULARY

    assert set(MATERIAL_VOCABULARY) == carbon.known_materials()
    assert tuple(sorted(MATERIAL_VOCABULARY)) == MATERIAL_VOCABULARY


def test_the_estimate_request_carries_the_vocabulary_as_data() -> None:
    import json

    from app.identify.openai_request import MATERIAL_VOCABULARY, build_estimate_request
    from app.schemas import VisionResult

    vision = VisionResult.model_validate(
        {"label": "keyboard", "class": "untracked", "confidence": 0.9}
    )
    request = build_estimate_request("keyboard", vision, 685.0, "test-text-model")
    data = json.loads(request["messages"][1]["content"][1]["text"])
    assert data["materials"] == list(MATERIAL_VOCABULARY)
