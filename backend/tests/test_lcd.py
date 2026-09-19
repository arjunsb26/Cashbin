"""LCD builders and truncation. PLAN.md section 19 lists this test as required."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
