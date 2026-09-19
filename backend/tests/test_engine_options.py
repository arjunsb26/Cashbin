from __future__ import annotations

from datetime import date

from app.engine.options import (
    TONE_AMBER,
    TONE_GREEN,
    TONE_RED,
    by_option,
    score_options,
    summarise,
)
from app.engine.records import (
    Condition,
    EngineSettings,
    EstimateSource,
    ItemClass,
    ItemRecord,
    Option,
    OptionScore,
)
from tests.test_engine_cases import (
    KEYBOARD_ASSET,
    SETTINGS,
    bagel_record,
    charger_record,
    keyboard_record,
)

EVENT_DATE = date(2026, 9, 19)


def test_the_keyboard_shows_a_book_loss_against_a_zero_tax_basis() -> None:
    record = keyboard_record()
    scores = by_option(score_options(record, SETTINGS, KEYBOARD_ASSET))

    assert record.book_value_cents == 6000
    assert record.tax_basis_cents == 0

    trash = scores[Option.trash]
    assert trash.allowed is False
    assert trash.blocked_reason == "Electronics: check your state's disposal rule"
    assert trash.tax_effect_cents == 0
    assert "BONUS_100" in trash.rule_ids

    repair = scores[Option.repair]
    assert repair.net_after_tax_cents == 12000 - 1500

    ranking = summarise(list(scores.values()), SETTINGS)
    assert ranking.tone == TONE_RED
    assert ranking.best_option is Option.repair


def test_the_bagel_puts_donating_above_binning_and_asks_for_a_person() -> None:
    scores = score_options(bagel_record(), SETTINGS)
    table = by_option(scores)

    donate = table[Option.donate]
    trash = table[Option.trash]
    assert donate.needs_human_review is True
    assert "DONATE_FOOD" in donate.rule_ids
    assert donate.rank is not None
    assert trash.rank is not None
    assert donate.rank < trash.rank

    assert donate.kg_co2e is not None and trash.kg_co2e is not None
    assert donate.kg_co2e < 0 < trash.kg_co2e
    assert trash.kg_landfill == 0.095


def test_the_charger_may_not_be_binned_at_all() -> None:
    scores = score_options(charger_record(), SETTINGS)
    table = by_option(scores)

    trash = table[Option.trash]
    assert trash.allowed is False
    assert trash.rank is None
    assert trash.blocked_reason == "Electronics: check your state's disposal rule"

    recycle = table[Option.recycle]
    assert recycle.allowed is True
    assert recycle.rank == 1

    assert Option.donate not in table
    assert Option.resell not in table

    ranking = summarise(scores, SETTINGS)
    assert ranking.tone == TONE_RED
    assert ranking.best_option is Option.recycle


def test_an_option_the_table_does_not_offer_is_left_out_entirely() -> None:
    record = ItemRecord(
        event_id=9,
        label="pizza box",
        item_class=ItemClass.inventory,
        mass_g=300.0,
        event_date=EVENT_DATE,
        material_mix={"corrugated_containers": 1.0},
        cost_basis_cents=49,
    )
    options = {score.option for score in score_options(record, SETTINGS)}
    assert Option.donate not in options
    assert Option.repair not in options
    assert Option.trash in options


def test_ties_inside_the_window_are_broken_by_lower_carbon() -> None:
    scores = [
        OptionScore(option=Option.trash, net_after_tax_cents=100, kg_co2e=0.5),
        OptionScore(option=Option.recycle, net_after_tax_cents=80, kg_co2e=-0.2),
        OptionScore(option=Option.resell, net_after_tax_cents=60, kg_co2e=-1.0),
    ]
    settings = EngineSettings(tie_break_cents=50)
    ordered = _rank_for_test(scores, settings)
    assert [s.option for s in ordered] == [Option.resell, Option.recycle, Option.trash]


def test_a_gap_wider_than_the_tie_window_is_not_a_tie() -> None:
    scores = [
        OptionScore(option=Option.trash, net_after_tax_cents=1000, kg_co2e=0.5),
        OptionScore(option=Option.recycle, net_after_tax_cents=100, kg_co2e=-5.0),
    ]
    settings = EngineSettings(tie_break_cents=50)
    ordered = _rank_for_test(scores, settings)
    assert [s.option for s in ordered] == [Option.trash, Option.recycle]


def test_an_unknown_carbon_figure_never_wins_a_tie() -> None:
    scores = [
        OptionScore(option=Option.trash, net_after_tax_cents=100, kg_co2e=None),
        OptionScore(option=Option.recycle, net_after_tax_cents=100, kg_co2e=0.4),
    ]
    ordered = _rank_for_test(scores, EngineSettings())
    assert ordered[0].option is Option.recycle


def _rank_for_test(scores: list[OptionScore], settings: EngineSettings) -> list[OptionScore]:
    from app.engine.options import _rank

    _rank(scores, settings)
    return sorted(scores, key=lambda s: s.rank or 0)


def test_saved_if_followed_is_the_gap_between_best_and_the_bin() -> None:
    record = ItemRecord(
        event_id=10,
        label="tablet",
        item_class=ItemClass.untracked,
        mass_g=400.0,
        event_date=EVENT_DATE,
        material_mix={"portable_electronic_devices": 1.0},
        fmv_mid=20000,
        fmv_source=EstimateSource.model_estimate,
    )
    scores = score_options(record, SETTINGS)
    ranking = summarise(scores, SETTINGS)
    table = by_option(scores)
    assert ranking.best_option is Option.resell
    expected = table[Option.resell].net_after_tax_cents - table[Option.trash].net_after_tax_cents
    assert ranking.saved_if_followed_cents == expected


def test_the_tone_is_green_when_the_bin_was_already_the_right_answer() -> None:
    record = ItemRecord(
        event_id=11,
        label="paper napkins",
        item_class=ItemClass.inventory,
        mass_g=2.0,
        event_date=EVENT_DATE,
        material_mix={"mixed_paper": 1.0},
        cost_basis_cents=2,
    )
    scores = score_options(record, SETTINGS)
    ranking = summarise(scores, SETTINGS)
    assert ranking.tone == TONE_GREEN
    assert ranking.saved_if_followed_cents == 0


def test_the_tone_is_amber_when_money_was_left_on_the_table() -> None:
    record = ItemRecord(
        event_id=12,
        label="mouse",
        item_class=ItemClass.untracked,
        mass_g=75.0,
        event_date=EVENT_DATE,
        material_mix={"electronic_peripherals": 1.0},
        fmv_mid=1500,
        fmv_source=EstimateSource.model_estimate,
    )
    ranking = summarise(score_options(record, SETTINGS), SETTINGS)
    assert ranking.tone == TONE_AMBER


def test_repair_adds_back_the_replacement_it_avoids() -> None:
    record = ItemRecord(
        event_id=13,
        label="monitor",
        item_class=ItemClass.untracked,
        mass_g=3000.0,
        event_date=EVENT_DATE,
        material_mix={"flat_panel_displays": 1.0},
        condition=Condition.broken,
        repair_mid=4000,
        repair_source=EstimateSource.model_estimate,
        replacement_cents=15000,
    )
    table = by_option(score_options(record, SETTINGS))
    repair = table[Option.repair]
    assert repair.cash_cents == -4000
    assert repair.net_after_tax_cents == 11000
    assert any("replacement" in note for note in repair.notes)


def test_an_option_with_an_unknown_material_says_so_and_carries_no_number() -> None:
    record = ItemRecord(
        event_id=14,
        label="mystery lump",
        item_class=ItemClass.untracked,
        mass_g=120.0,
        event_date=EVENT_DATE,
        material_mix={"unobtainium": 1.0},
    )
    trash = by_option(score_options(record, SETTINGS))[Option.trash]
    assert trash.kg_co2e is None
    assert any("unobtainium" in note for note in trash.notes)


def test_the_greenest_option_is_reported_alongside_the_cheapest() -> None:
    scores = score_options(bagel_record(), SETTINGS)
    table = by_option(scores)
    ranking = summarise(scores, SETTINGS)
    # Donating, reselling and repairing all displace a new item, so they share
    # the same source reduction factor and tie for greenest.
    assert ranking.greenest_option in {Option.donate, Option.resell}
    assert ranking.greenest_option is not None
    greenest = table[ranking.greenest_option]
    trash = table[Option.trash]
    assert greenest.kg_co2e == table[Option.donate].kg_co2e
    assert greenest.kg_co2e is not None
    assert trash.kg_co2e is not None
    assert greenest.kg_co2e < trash.kg_co2e


def test_every_score_carries_its_event_id() -> None:
    for score in score_options(bagel_record(), SETTINGS):
        assert score.event_id == 2


# --- tone, PLAN.md section 21a item 10 ----------------------------------------


def test_the_tone_is_amber_when_only_the_carbon_is_better() -> None:
    """A bagel: pennies apart on money, far apart on carbon. That is amber."""
    scores = score_options(bagel_record(), SETTINGS)
    ranking = summarise(scores, SETTINGS)
    table = by_option(scores)
    money_gap = (
        table[Option.donate].net_after_tax_cents - table[Option.trash].net_after_tax_cents
    )
    assert money_gap < SETTINGS.tie_break_cents
    assert ranking.best_option is Option.donate
    assert ranking.tone == TONE_AMBER


def test_the_tone_is_red_whenever_the_bin_is_blocked() -> None:
    keyboard = summarise(score_options(keyboard_record(), SETTINGS, KEYBOARD_ASSET), SETTINGS)
    assert keyboard.tone == TONE_RED
    charger = summarise(score_options(charger_record(), SETTINGS), SETTINGS)
    assert charger.tone == TONE_RED


def test_the_tone_is_green_when_the_best_option_is_the_bin() -> None:
    record = ItemRecord(
        event_id=21,
        label="paper napkins",
        item_class=ItemClass.inventory,
        mass_g=2.0,
        event_date=EVENT_DATE,
        material_mix={"mixed_paper": 1.0},
        cost_basis_cents=2,
    )
    scores = score_options(record, SETTINGS)
    ranking = summarise(scores, SETTINGS)
    table = by_option(scores)
    best = table[ranking.best_option] if ranking.best_option else None
    trash = table[Option.trash]
    assert best is not None and best.kg_co2e is not None and trash.kg_co2e is not None
    assert abs(best.kg_co2e - trash.kg_co2e) < SETTINGS.tone_co2e_kg
    assert ranking.tone == TONE_GREEN


def test_an_unknown_carbon_figure_never_buys_a_green_tone() -> None:
    """No factor means no claim that the bin was fine, however close the money is."""
    record = ItemRecord(
        event_id=22,
        label="mystery lump",
        item_class=ItemClass.untracked,
        mass_g=100.0,
        event_date=EVENT_DATE,
        material_mix={"unobtainium": 1.0},
        scrap_cents=10,
        scrap_source=EstimateSource.model_estimate,
    )
    scores = score_options(record, SETTINGS)
    assert all(score.kg_co2e is None for score in scores)
    table = by_option(scores)
    ranking = summarise(scores, SETTINGS)
    assert ranking.best_option is Option.recycle
    money_gap = (
        table[Option.recycle].net_after_tax_cents - table[Option.trash].net_after_tax_cents
    )
    assert 0 < money_gap < SETTINGS.tie_break_cents
    assert ranking.tone == TONE_AMBER


def test_the_carbon_threshold_is_a_setting() -> None:
    assert SETTINGS.tone_co2e_kg == 0.02
    wide = EngineSettings(tone_co2e_kg=10.0)
    assert summarise(score_options(bagel_record(), wide), wide).tone == TONE_GREEN
