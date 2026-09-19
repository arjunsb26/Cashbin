from __future__ import annotations

from datetime import date

import pytest
from app.engine import rules, tax
from app.engine.records import (
    Condition,
    EngineSettings,
    EstimateSource,
    ItemClass,
    ItemRecord,
    Option,
)

from tests.test_engine_cases import KEYBOARD_ASSET, keyboard_record

SETTINGS = EngineSettings()
EVENT_DATE = date(2026, 9, 19)


def record(**overrides: object) -> ItemRecord:
    base = {
        "event_id": 1,
        "label": "thing",
        "item_class": ItemClass.untracked,
        "mass_g": 100.0,
        "event_date": EVENT_DATE,
        "material_mix": {"mixed_plastics": 1.0},
    }
    base.update(overrides)
    return ItemRecord(**base)


# --- the rule file -----------------------------------------------------------


def test_every_rule_the_engine_cites_is_in_the_file() -> None:
    for rule_id in (
        "ABANDON",
        "RECAPTURE",
        "BONUS_100",
        "DONATE_FOOD",
        "DONATE_EQUIP",
        "INV_COGS",
        "EWASTE",
    ):
        rule = rules.get(rule_id)
        assert rule.plain_text
        assert rule.title


def test_an_unknown_rule_id_raises() -> None:
    with pytest.raises(rules.UnknownRule):
        rules.get("NOT_A_RULE")


def test_donation_rules_always_ask_for_a_person() -> None:
    assert rules.get("DONATE_FOOD").needs_human_review
    assert rules.get("DONATE_EQUIP").needs_human_review


# --- rounding ----------------------------------------------------------------


def test_tax_rounds_half_up_to_whole_cents() -> None:
    assert tax.apply_rate(0.21, 100) == 21
    assert tax.apply_rate(0.5, 5) == 3
    assert tax.apply_rate(0.21, 0) == 0


# --- the food donation worked example ----------------------------------------


def test_food_donation_worked_example() -> None:
    """PLAN.md section 10: cost 100.00, value 300.00, enhanced 200.00."""
    result = tax.food_donation_deduction(10000, 30000)
    assert result.enhanced_cents == 20000
    assert result.incremental_cents == 10000


def test_food_donation_is_capped_at_twice_cost() -> None:
    result = tax.food_donation_deduction(10000, 100000)
    assert result.enhanced_cents == 20000


def test_food_donation_never_goes_below_cost() -> None:
    result = tax.food_donation_deduction(10000, 5000)
    assert result.enhanced_cents == 10000
    assert result.incremental_cents == 0


def test_food_donation_flows_into_the_option() -> None:
    item = record(
        item_class=ItemClass.inventory,
        material_mix={"food_waste": 1.0},
        cost_basis_cents=10000,
        fmv_mid=30000,
        fmv_source=EstimateSource.catalog,
    )
    effect = tax.tax_effect_for(Option.donate, item, SETTINGS)
    assert effect is not None
    assert effect.deduction_cents == 10000
    assert effect.tax_effect_cents == 2100
    assert effect.needs_human_review
    assert effect.rule_ids == ("DONATE_FOOD",)


# --- trash -------------------------------------------------------------------


def test_trash_fixed_asset_deducts_the_remaining_tax_basis() -> None:
    item = record(item_class=ItemClass.fixed_asset, tax_basis_cents=6000)
    effect = tax.tax_effect_for(Option.trash, item, SETTINGS)
    assert effect is not None
    assert effect.deduction_cents == 6000
    assert effect.tax_effect_cents == 1260
    assert "ABANDON" in effect.rule_ids


def test_trash_a_bonus_asset_deducts_nothing_and_says_why() -> None:
    effect = tax.tax_effect_for(
        Option.trash, keyboard_record(), SETTINGS, KEYBOARD_ASSET
    )
    assert effect is not None
    assert effect.deduction_cents == 0
    assert effect.tax_effect_cents == 0
    assert "BONUS_100" in effect.rule_ids


def test_trash_inventory_gives_no_extra_deduction() -> None:
    item = record(item_class=ItemClass.inventory, cost_basis_cents=500)
    effect = tax.tax_effect_for(Option.trash, item, SETTINGS)
    assert effect is not None
    assert effect.tax_effect_cents == 0
    assert effect.rule_ids == ("INV_COGS",)


def test_trash_untracked_is_all_zero() -> None:
    effect = tax.tax_effect_for(Option.trash, record(), SETTINGS)
    assert effect is not None
    assert effect.cash_cents == 0
    assert effect.tax_effect_cents == 0


def test_a_disposal_fee_shows_as_cash_out() -> None:
    settings = EngineSettings(disposal_fee_cents=25)
    effect = tax.tax_effect_for(Option.trash, record(), settings)
    assert effect is not None
    assert effect.cash_cents == -25


# --- blocked trash -----------------------------------------------------------


@pytest.mark.parametrize("flag", ["electronics", "battery"])
def test_trash_is_blocked_for_electronics_and_batteries(flag: str) -> None:
    item = record(regulatory_flags=[flag])
    effect = tax.tax_effect_for(Option.trash, item, SETTINGS)
    assert effect is not None
    assert effect.allowed is False
    assert effect.blocked_reason == "Electronics: check your state's disposal rule"
    assert "EWASTE" in effect.rule_ids


def test_recycling_electronics_is_never_blocked() -> None:
    item = record(regulatory_flags=["electronics"])
    effect = tax.tax_effect_for(Option.recycle, item, SETTINGS)
    assert effect is not None
    assert effect.allowed is True


# --- recycle -----------------------------------------------------------------


def test_recycle_pays_scrap_less_the_fee() -> None:
    settings = EngineSettings(recycle_fee_cents=40)
    item = record(scrap_cents=150)
    effect = tax.tax_effect_for(Option.recycle, item, settings)
    assert effect is not None
    assert effect.cash_cents == 110


def test_recycle_a_fixed_asset_keeps_the_abandonment_deduction() -> None:
    item = record(item_class=ItemClass.fixed_asset, tax_basis_cents=6000, scrap_cents=200)
    effect = tax.tax_effect_for(Option.recycle, item, SETTINGS)
    assert effect is not None
    assert effect.cash_cents == 200
    assert effect.tax_effect_cents == 1260


def test_recycle_inventory_matches_trash_on_tax() -> None:
    item = record(item_class=ItemClass.inventory, cost_basis_cents=500, scrap_cents=10)
    effect = tax.tax_effect_for(Option.recycle, item, SETTINGS)
    assert effect is not None
    assert effect.tax_effect_cents == 0
    assert effect.cash_cents == 10


# --- resell ------------------------------------------------------------------


def test_resell_above_basis_is_taxed_and_notes_recapture() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        tax_basis_cents=1000,
        fmv_mid=5000,
        fmv_source=EstimateSource.model_estimate,
    )
    effect = tax.tax_effect_for(Option.resell, item, SETTINGS)
    assert effect is not None
    assert effect.gain_cents == 4000
    assert effect.tax_effect_cents == -840
    assert "RECAPTURE" in effect.rule_ids
    assert any("ordinary income" in note for note in effect.notes)


def test_resell_below_basis_is_a_tax_benefit() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        tax_basis_cents=5000,
        fmv_mid=1000,
        fmv_source=EstimateSource.model_estimate,
    )
    effect = tax.tax_effect_for(Option.resell, item, SETTINGS)
    assert effect is not None
    assert effect.gain_cents == -4000
    assert effect.tax_effect_cents == 840


def test_resell_inventory_measures_the_gain_against_cost() -> None:
    item = record(
        item_class=ItemClass.inventory,
        cost_basis_cents=200,
        fmv_mid=500,
        fmv_source=EstimateSource.catalog,
    )
    effect = tax.tax_effect_for(Option.resell, item, SETTINGS)
    assert effect is not None
    assert effect.gain_cents == 300
    assert effect.cash_cents == 500


def test_resell_untracked_treats_the_whole_price_as_gain_and_asks_for_review() -> None:
    item = record(fmv_mid=5000, fmv_source=EstimateSource.model_estimate)
    effect = tax.tax_effect_for(Option.resell, item, SETTINGS)
    assert effect is not None
    assert effect.gain_cents == 5000
    assert effect.tax_effect_cents == -1050
    assert effect.needs_human_review


def test_resell_is_not_offered_without_a_value() -> None:
    assert tax.tax_effect_for(Option.resell, record(), SETTINGS) is None


# --- donate ------------------------------------------------------------------


def test_donate_equipment_takes_the_lower_of_value_and_basis() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        tax_basis_cents=3000,
        fmv_mid=9000,
        fmv_source=EstimateSource.model_estimate,
    )
    effect = tax.tax_effect_for(Option.donate, item, SETTINGS)
    assert effect is not None
    assert effect.deduction_cents == 3000
    assert effect.needs_human_review
    assert effect.rule_ids == ("DONATE_EQUIP",)


def test_donate_is_not_offered_for_non_food_inventory() -> None:
    item = record(
        item_class=ItemClass.inventory,
        material_mix={"corrugated_containers": 1.0},
        cost_basis_cents=100,
        fmv_mid=300,
        fmv_source=EstimateSource.catalog,
    )
    assert tax.tax_effect_for(Option.donate, item, SETTINGS) is None


def test_donate_is_not_offered_for_untracked_items() -> None:
    item = record(fmv_mid=5000, fmv_source=EstimateSource.model_estimate)
    assert tax.tax_effect_for(Option.donate, item, SETTINGS) is None


# --- repair ------------------------------------------------------------------


def test_repair_is_offered_for_a_broken_asset_with_a_known_replacement() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        condition=Condition.broken,
        repair_mid=1500,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=12000,
    )
    effect = tax.tax_effect_for(Option.repair, item, SETTINGS)
    assert effect is not None
    assert effect.cash_cents == -1500


def test_repair_is_not_offered_for_a_working_item() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        condition=Condition.working,
        repair_mid=1500,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=12000,
    )
    assert tax.tax_effect_for(Option.repair, item, SETTINGS) is None


def test_repair_is_not_offered_without_a_replacement_price() -> None:
    item = record(
        item_class=ItemClass.fixed_asset,
        condition=Condition.broken,
        repair_mid=1500,
        repair_source=EstimateSource.model_estimate,
    )
    assert tax.tax_effect_for(Option.repair, item, SETTINGS) is None


def test_repair_is_not_offered_for_inventory() -> None:
    item = record(
        item_class=ItemClass.inventory,
        condition=Condition.broken,
        repair_mid=100,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=500,
    )
    assert tax.tax_effect_for(Option.repair, item, SETTINGS) is None


def test_repair_an_untracked_item_is_offered() -> None:
    item = record(
        condition=Condition.unknown,
        repair_mid=800,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=5000,
    )
    effect = tax.tax_effect_for(Option.repair, item, SETTINGS)
    assert effect is not None
    assert effect.cash_cents == -800


# --- the whole table ---------------------------------------------------------


@pytest.mark.parametrize("item_class", list(ItemClass))
@pytest.mark.parametrize("option", list(Option))
def test_every_option_for_every_class_returns_an_effect_or_nothing(
    option: Option, item_class: ItemClass
) -> None:
    """The full grid from PLAN.md section 10, with everything the record can hold."""
    item = record(
        item_class=item_class,
        material_mix={"food_waste": 1.0},
        condition=Condition.broken,
        cost_basis_cents=10000,
        tax_basis_cents=3000,
        book_value_cents=4000,
        fmv_mid=30000,
        fmv_source=EstimateSource.model_estimate,
        repair_mid=1500,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=20000,
        scrap_cents=50,
    )
    effect = tax.tax_effect_for(option, item, SETTINGS)
    not_offered = {
        (Option.donate, ItemClass.untracked),
        (Option.repair, ItemClass.inventory),
    }
    if (option, item_class) in not_offered:
        assert effect is None
    else:
        assert effect is not None
        for rule_id in effect.rule_ids:
            assert rules.get(rule_id).id == rule_id
