"""LCD builders and truncation. PLAN.md section 19 lists this test as required."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.engine.records import ItemClass
from app.notify import lcd
from app.schemas import LCD_BIG_MAX, LCD_LINE_MAX


def test_idle_thinking_offline_shapes() -> None:
    assert lcd.idle().model_dump() == {"type": "screen", "s": "idle"}
    assert lcd.thinking().model_dump() == {"type": "screen", "s": "thinking"}
    assert lcd.offline().model_dump() == {"type": "screen", "s": "offline"}


def test_result_matches_the_contract_example() -> None:
    """The example in PLAN.md section 6 has a 21 character second line, so it lands cut at 20."""
    screen = lcd.result("Keyboard", "-$20", "Removed from register", "amber")
    assert screen.model_dump() == {
        "type": "screen",
        "s": "result",
        "l1": "Keyboard",
        "big": "-$20",
        "l2": "Removed from registe",
        "c": "amber",
    }


def test_ask_has_the_contract_wording() -> None:
    screen = lcd.ask()
    assert screen.l1 == "Not sure"
    assert screen.l2 == "Check the dashboard"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Keyboard", "Keyboard"),
        ("Removed from register", "Removed from registe"),
        ("Mechanical keyboard with wrist rest", "Mechanical keyboard"),
        ("x" * 20, "x" * 20),
        ("x" * 21, "x" * 20),
    ],
)
def test_fit_line(raw: str, expected: str) -> None:
    result = lcd.fit_line(raw)
    assert result == expected
    assert len(result) <= LCD_LINE_MAX


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-$20", "-$20"),
        ("-$1,234", "-$1,234"),
        ("-$1,234,567", "-$1,234"),
        ("212 g", "212g"),
        ("", ""),
    ],
)
def test_fit_big(raw: str, expected: str) -> None:
    result = lcd.fit_big(raw)
    assert result == expected
    assert len(result) <= LCD_BIG_MAX


def test_long_input_never_reaches_the_bin() -> None:
    """The builder truncates, so an over-long label cannot become an invalid frame."""
    screen = lcd.result(
        "A very long item label that nobody expected",
        "-$1,234,567.89",
        "This explanation is far too long for the screen",
        "red",
    )
    assert len(screen.l1) <= LCD_LINE_MAX
    assert len(screen.big) <= LCD_BIG_MAX
    assert len(screen.l2) <= LCD_LINE_MAX
    assert screen.c == "red"


def test_accents_fold_and_unsupported_glyphs_are_dropped() -> None:
    """The LCD font is ASCII only, so the backend folds before it sends."""
    assert lcd.fit_line("Café cup") == "Cafe cup"
    assert lcd.fit_line("pizza \U0001f355 slice") == "pizza slice"


def test_newlines_and_runs_of_space_collapse() -> None:
    assert lcd.fit_line("  Cracked\n\tPhone  ") == "Cracked Phone"


def test_the_model_cuts_an_oversized_field_built_by_hand() -> None:
    """A screen built without the builders is cut the same way, so nothing bypasses the limit."""
    screen = lcd.ScreenResult(l1="y" * 60, big="-$1,234,567", l2="z" * 60, c="green")
    assert len(screen.l1) == LCD_LINE_MAX
    assert len(screen.l2) == LCD_LINE_MAX
    assert screen.big == "-$1,234"


def test_the_colour_enum_is_still_closed() -> None:
    with pytest.raises(ValidationError):
        lcd.ScreenResult(l1="ok", big="-$20", l2="ok", c="purple")


# What a toss means, in two words --------------------------------------------


@pytest.mark.parametrize(
    ("item_class", "cents", "kind", "line1", "big"),
    [
        (ItemClass.inventory, 418, "", "Wasted", "$4.18"),
        (ItemClass.inventory, 100, "", "Wasted", "$1.00"),
        (ItemClass.fixed_asset, 45000, "", "Written off", "$450.00"),
        (ItemClass.untracked, 9000, "", "Worth about", "$90.00"),
        # A sign on the bin reads as a fault, so the word carries the direction.
        (ItemClass.inventory, -418, "", "Wasted", "$4.18"),
        # Packaging leads with the carbon, and the figure is grams.
        (ItemClass.inventory, 212, lcd.PACKAGING, "CO2e avoided", "212g"),
        (ItemClass.untracked, 2412, lcd.PACKAGING, "CO2e avoided", "2,412g"),
    ],
)
def test_headline_for_every_class(
    item_class: ItemClass, cents: int, kind: str, line1: str, big: str
) -> None:
    drawn_line, drawn_big = lcd.headline_for(item_class, cents, kind)
    assert (drawn_line, drawn_big) == (line1, big)
    assert len(drawn_line) <= LCD_LINE_MAX
    assert len(drawn_big) <= LCD_BIG_MAX


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "$0.00"),
        (418, "$4.18"),
        (999999, "$9,999"),
        # Past the width the cents go first, then the comma, then thousands.
        (10000, "$100.00"),
        (1000000, "$10,000"),
        (12345678, "$123456"),
        (999999999, "$10000k"),
    ],
)
def test_the_big_figure_is_cut_down_until_the_bin_can_draw_it(
    cents: int, expected: str
) -> None:
    drawn = lcd.big_money(cents)
    assert drawn == expected
    assert len(drawn) <= LCD_BIG_MAX


def test_every_class_and_size_fits_the_screen() -> None:
    """No class, and no figure a demo can produce, can overflow either field."""
    for item_class in ItemClass:
        for cents in (0, 1, 99, 100, 9999, 10000, 99999, 1234567, 99999999):
            line1, big = lcd.headline_for(item_class, cents)
            assert len(line1) <= LCD_LINE_MAX and len(big) <= LCD_BIG_MAX
            assert " " not in big


def test_a_carbon_figure_turns_into_kilograms_when_it_has_to() -> None:
    assert lcd.big_grams(212) == "212g"
    assert lcd.big_grams(2412) == "2,412g"
    assert lcd.big_grams(124120) == "124.1kg"
    assert lcd.big_grams(9999999) == "10t"
    for grams in (0, 1, 999, 1000, 99999, 9999999, 999999999):
        assert len(lcd.big_grams(grams)) <= LCD_BIG_MAX


# The resting screen ----------------------------------------------------------


def test_the_idle_screen_shows_the_running_total() -> None:
    screen = lcd.idle_screen(4180, 2412, 7)
    assert screen.model_dump() == {
        "type": "screen",
        "s": "result",
        "l1": "In the bin",
        "big": "$41.80",
        "l2": "2,412 g, 7 items",
        "c": "neutral",
    }


def test_the_idle_screen_says_one_item_when_there_is_one() -> None:
    assert lcd.idle_screen(500, 95, 1).l2 == "95 g, 1 item"


def test_an_empty_bin_says_what_would_fill_it() -> None:
    screen = lcd.idle_screen(0, 0.0, 0)
    assert screen.l2 == "Nothing in it yet"
    assert screen.big == "$0.00"


def test_a_full_bin_still_fits_the_screen() -> None:
    screen = lcd.idle_screen(1234567, 48123.4, 412)
    assert len(screen.l1) <= LCD_LINE_MAX
    assert len(screen.big) <= LCD_BIG_MAX
    assert len(screen.l2) <= LCD_LINE_MAX
