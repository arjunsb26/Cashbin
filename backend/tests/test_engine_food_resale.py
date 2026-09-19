"""Food in the bin cannot be resold, and the donation deduction is not zero.

PLAN.md section 21a item 9. Resell stays in the list as a blocked row with a
reason, exactly like blocked trash, so nothing disappears from the ticket. The
catalog carries the business cost for food, not the shelf price, so the section
10 enhanced deduction has a mark up to work on and the bagel case reads the way
the M3 acceptance check says it should.
"""

from __future__ import annotations

from app.engine import options, rules, tax
from app.engine.records import (
    EngineSettings,
    Option,
    catalog_by_label,
    load_catalog,
)
from tests.test_engine_cases import (
    SETTINGS,
    bagel_record,
    keyboard_record,
)

FOOD_LABELS = (
    "pizza slice",
    "bagel",
    "cookie",
    "banana",
    "apple",
    "chips bag",
    "soda can",
    "water bottle full",
    "pasta box",
    "wrap",
    "sandwich",
)


def test_every_food_row_carries_the_food_flag() -> None:
    table = catalog_by_label()
    for label in FOOD_LABELS:
        assert "food" in table[label].regulatory_flags, label


def test_nothing_but_food_carries_the_food_flag() -> None:
    for item in load_catalog():
        if item.label in FOOD_LABELS:
            continue
        assert "food" not in item.regulatory_flags, item.label


def test_food_cost_is_half_the_retail_value_and_says_so() -> None:
    for label in FOOD_LABELS:
        item = catalog_by_label()[label]
        assert item.fmv_per_kg_cents is not None, label
        assert item.price_source is not None, label
        assert item.price_source.startswith("estimate: 50 percent of retail "), label
        # Half of retail, give or take the cent that rounding to whole cents costs.
        if item.price_per_kg_cents is not None:
            assert abs(item.price_per_kg_cents * 2 - item.fmv_per_kg_cents) <= 2, label
        else:
            assert item.unit_cost_cents is not None, label
            assert item.unit_mass_g, label
            retail_unit = item.fmv_per_kg_cents * item.unit_mass_g / 1000.0
            assert abs(item.unit_cost_cents * 2 - retail_unit) <= 2, label


def test_the_food_resale_rule_is_a_policy_with_no_citation() -> None:
    rule = rules.get("FOOD_NO_RESALE")
    assert rule.citation_url is None
    assert rule.citations == ()
    assert rule.plain_text


def test_resell_is_blocked_for_food_with_a_reason_a_person_can_read() -> None:
    effect = tax.tax_effect_for(Option.resell, bagel_record(), SETTINGS)
    assert effect is not None
    assert effect.allowed is False
    assert effect.blocked_reason == "Food in the bin cannot be resold"
    assert "FOOD_NO_RESALE" in effect.rule_ids


def test_a_blocked_resale_row_still_appears_and_never_ranks() -> None:
    scores = options.by_option(options.score_options(bagel_record(), SETTINGS))
    resell = scores[Option.resell]
    assert resell.allowed is False
    assert resell.rank is None
    assert resell.blocked_reason == "Food in the bin cannot be resold"


def test_resale_is_not_blocked_for_equipment() -> None:
    effect = tax.tax_effect_for(Option.resell, keyboard_record(), SETTINGS)
    assert effect is not None
    assert effect.allowed is True
    assert effect.blocked_reason is None


def test_donating_the_bagel_ranks_first_and_asks_for_a_person() -> None:
    scores = options.score_options(bagel_record(), SETTINGS)
    table = options.by_option(scores)
    donate = table[Option.donate]
    assert donate.rank == 1
    assert donate.needs_human_review is True
    assert "DONATE_FOOD" in donate.rule_ids
    # A real deduction, not the zero the retail-priced catalog used to give.
    assert donate.tax_effect_cents > 0
    assert donate.net_after_tax_cents > table[Option.trash].net_after_tax_cents
    ranking = options.summarise(scores, SETTINGS)
    assert ranking.best_option is Option.donate


def test_engine_settings_are_built_from_the_live_settings_object() -> None:
    from app.config import Settings

    live = Settings(tax_rate=0.3, disposal_fee_cents=25, recycle_fee_cents=10)
    built = EngineSettings.from_settings(live)
    assert built.tax_rate == 0.3
    assert built.disposal_fee_cents == 25
    assert built.recycle_fee_cents == 10
    assert built.capitalization_threshold_cents == live.capitalization_threshold_cents
    assert built.tie_break_cents == EngineSettings().tie_break_cents
