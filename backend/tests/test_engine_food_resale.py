"""Food in the bin cannot be resold, and the donation deduction is not zero.

PLAN.md section 21a item 9. Resell stays in the list as a blocked row with a
reason, exactly like blocked trash, so nothing disappears from the ticket. The
catalog carries the business cost for food, not the shelf price, so the section
10 enhanced deduction has a mark up to work on and the bagel case reads the way
the M3 acceptance check says it should.
"""

from __future__ import annotations

from app.engine import carbon, options, rules, tax
from app.engine.records import (
    Condition,
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


def test_the_food_flag_follows_the_material_and_not_a_list() -> None:
    """A row is flagged food when most of its mass is food, and only then.

    This used to be a fixed list of labels, which meant the catalog could not grow a food
    row without the rule quietly stopping short of it. The material mix is the fact; the
    flag is supposed to agree with it.
    """
    for item in load_catalog():
        mostly_food = sum(
            share
            for material, share in item.material_mix.items()
            if carbon.is_food_material(material)
        )
        flagged = "food" in item.regulatory_flags
        assert flagged == (mostly_food >= 0.5), f"{item.label}: {mostly_food:.2f} food"


def test_every_label_the_resale_rule_names_is_still_flagged() -> None:
    table = catalog_by_label()
    for label in FOOD_LABELS:
        assert "food" in table[label].regulatory_flags, label


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
    """The food rule is about food. A working keyboard is a thing somebody would buy."""
    working = keyboard_record().model_copy(update={"condition": Condition.working})
    effect = tax.tax_effect_for(Option.resell, working, SETTINGS)
    assert effect is not None
    assert effect.allowed is True
    assert effect.blocked_reason is None


def test_a_broken_thing_is_not_offered_for_sale() -> None:
    """PLAN.md 21a item 48. Nobody is buying it, so the bin should not suggest it."""
    broken = keyboard_record().model_copy(update={"condition": Condition.broken})
    effect = tax.tax_effect_for(Option.resell, broken, SETTINGS)
    assert effect is not None
    assert effect.allowed is False
    assert effect.blocked_reason == tax.BROKEN_NOT_SELLABLE


def test_a_bagel_out_of_a_bin_is_not_offered_to_a_charity() -> None:
    """PLAN.md 21a item 48. Nobody donates food somebody already opened.

    The arithmetic underneath is unchanged and still right, which is what the next test
    reads. What changed is that the bin no longer says it out loud about an opened bagel.
    """
    scores = options.score_options(bagel_record(), SETTINGS)
    donate = options.by_option(scores)[Option.donate]
    assert donate.allowed is False
    assert donate.blocked_reason == tax.FOOD_NOT_SEALED
    assert options.summarise(scores, SETTINGS).best_option is not Option.donate


def test_sealed_food_still_earns_the_enhanced_deduction() -> None:
    sealed = bagel_record().model_copy(update={"description": "a sealed bagel in its bag"})
    scores = options.score_options(sealed, SETTINGS)
    table = options.by_option(scores)
    donate = table[Option.donate]
    assert donate.allowed is True
    assert donate.rank == 1
    assert donate.needs_human_review is True
    assert "DONATE_FOOD" in donate.rule_ids
    # A real deduction, not the zero the retail-priced catalog used to give.
    assert donate.tax_effect_cents > 0
    assert donate.net_after_tax_cents > table[Option.trash].net_after_tax_cents
    assert options.summarise(scores, SETTINGS).best_option is Option.donate


def test_engine_settings_are_built_from_the_live_settings_object() -> None:
    from app.config import Settings

    live = Settings(_env_file=None, tax_rate=0.3, disposal_fee_cents=25, recycle_fee_cents=10)
    built = EngineSettings.from_settings(live)
    assert built.tax_rate == 0.3
    assert built.disposal_fee_cents == 25
    assert built.recycle_fee_cents == 10
    assert built.capitalization_threshold_cents == live.capitalization_threshold_cents
    assert built.tie_break_cents == EngineSettings().tie_break_cents
