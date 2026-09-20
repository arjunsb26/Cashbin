"""Every line the bin can draw, read as a person reads it.

DESIGN.md section 8 and the 20 character limit in PLAN.md section 6. `app/pipeline.py`
composes line 2 out of three fixed tables, so the whole vocabulary of that line is a short
list and can be checked one line at a time rather than hoped about.

The known bad line was "No bin. Repair it" on a nine dollar charger, which read as advice to
take a charger to a repair shop. That line is still right for a broken laptop, and PLAN.md
21a item 17 is what stops it landing on the cheap things. The check that it no longer lands
there is in `test_engine_tax.py`; what is checked here is the wording itself.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.engine.options import Ranking
from app.engine.records import ItemClass as EngineClass
from app.engine.records import ItemRecord as EngineRecord
from app.engine.records import Option
from app.notify import lcd
from app.pipeline import BINNED, BLOCKED_ADVICE, BLOCKED_ONLY, FINE_TO_BIN, advice_line
from app.schemas import LCD_BIG_MAX, LCD_LINE_MAX

# Marks and words no line the bin draws may carry. CLAUDE.md "Writing" and "What users see".
BANNED_MARKS = ("\u2014", "\u2013", "->", "\u2192", "!", "...", "\u2026")
BANNED_WORDS = (
    "error",
    "null",
    "none",
    "undefined",
    "stub",
    "openai",
    "provider",
    "pipeline",
    "backend",
    "api",
    "json",
    "sorry",
)


def every_line_two() -> list[str]:
    """Every line 2 the pipeline can compose, from the three tables it composes them from."""
    lines = list(BLOCKED_ADVICE.values())
    lines.append(BLOCKED_ONLY)
    lines.append(FINE_TO_BIN)
    lines.append(BINNED[EngineClass.fixed_asset])
    return lines


def record(**kwargs: Any) -> EngineRecord:
    base: dict[str, Any] = {
        "event_id": 1,
        "label": "bagel",
        "class": EngineClass.inventory,
        "mass_g": 95.0,
        "event_date": date(2026, 9, 19),
    }
    base.update(kwargs)
    return EngineRecord.model_validate(base)


def ranking(best: Option | None) -> Ranking:
    return Ranking(
        best_option=best, greenest_option=best, saved_if_followed_cents=0, tone="amber"
    )


def test_every_line_the_bin_can_draw_fits_and_reads_as_a_sentence() -> None:
    for line in every_line_two():
        assert line, "a blank line 2 tells a person nothing"
        assert len(line) <= LCD_LINE_MAX, f"{line!r} is {len(line)} characters"
        assert lcd.fit_line(line) == line, f"{line!r} is cut by the bin"
        assert line == line.strip()
        assert line[0].isupper(), f"{line!r} does not start as a sentence"
        for mark in BANNED_MARKS:
            assert mark not in line, f"{line!r} carries {mark!r}"
        for word in BANNED_WORDS:
            assert word not in line.lower(), f"{line!r} says {word!r} to a person"


def test_the_composer_only_ever_returns_one_of_those_lines() -> None:
    """Whatever the engine ranks, line 2 comes out of the vocabulary above."""
    known = set(every_line_two())
    for cls in EngineClass:
        for best in [*Option, None]:
            for blocked in (True, False):
                line = advice_line(record(**{"class": cls}), ranking(best), blocked)
                assert line in known, f"{cls} {best} blocked={blocked} gave {line!r}"


def test_the_binned_line_says_the_bin_was_the_right_place() -> None:
    """PLAN.md 21a item 37. Nothing to argue about, so the bin does not argue.

    A tagged asset is the exception: it coming off the register is the news on that
    ticket, and worth more than telling somebody the bin was acceptable.
    """
    assert advice_line(record(), ranking(Option.trash), blocked=False) == FINE_TO_BIN
    assert advice_line(
        record(**{"class": EngineClass.untracked}), ranking(Option.trash), blocked=False
    ) == FINE_TO_BIN
    assert advice_line(
        record(**{"class": EngineClass.fixed_asset}), ranking(Option.trash), blocked=False
    ) == "Removed from books"


def test_a_blocked_bin_says_the_bin_is_closed_and_what_to_do_instead() -> None:
    assert advice_line(record(), ranking(Option.recycle), blocked=True) == "Recycle, not trash"
    assert advice_line(record(), ranking(Option.trash), blocked=True) == BLOCKED_ONLY
    assert advice_line(record(), ranking(None), blocked=True) == BLOCKED_ONLY


def test_the_other_screens_read_the_same_way() -> None:
    """The ask, idle, thinking and offline screens are copy too."""
    ask = lcd.ask()
    for line in (ask.l1, ask.l2):
        assert len(line) <= LCD_LINE_MAX
        assert line[0].isupper()
        for mark in BANNED_MARKS:
            assert mark not in line
    # The biggest figure the bin can be handed still fits the seven character field.
    built = lcd.result("Mechanical keyboard", lcd.fit_big("-$1,234,567.89"),
                       "Resell it, not trash",
                       "red")
    assert len(built.big) <= LCD_BIG_MAX
    assert len(built.l1) <= LCD_LINE_MAX
    assert len(built.l2) <= LCD_LINE_MAX


def test_a_label_a_person_writes_in_capitals_is_drawn_in_capitals() -> None:
    """The bin drew "Usb-c charger" before this. Nobody writes a charger's name that way."""
    from app.pipeline import title_for

    assert title_for("usb-c charger") == "USB-C charger"
    assert title_for("usb cable") == "USB cable"
    assert title_for("hdmi cable") == "HDMI cable"
    assert title_for("mechanical keyboard") == "Mechanical keyboard"
    assert title_for("bagel") == "Bagel"
    assert title_for("") == ""
    for label in ("usb-c charger", "hdmi cable", "cardboard box medium"):
        assert len(title_for(label)) <= LCD_LINE_MAX


# When the bin is allowed to just be a bin ------------------------------------


def _ranking_saving(option: Option | None, saved: int) -> Ranking:
    return Ranking(
        best_option=option,
        greenest_option=option,
        saved_if_followed_cents=saved,
        tone="amber",
    )


def test_a_bagel_worth_three_cents_more_donated_is_fine_to_bin() -> None:
    """PLAN.md 21a item 37. The user's words: if something is trash just say it is trash."""
    line = advice_line(record(), _ranking_saving(Option.donate, 3), blocked=False)
    assert line == FINE_TO_BIN


def test_a_mouse_worth_fifteen_dollars_resold_says_so() -> None:
    line = advice_line(record(), _ranking_saving(Option.resell, 1500), blocked=False)
    assert line == "Resell it, not trash"


def test_a_blocked_bin_always_names_the_option() -> None:
    """A phone may not go in the bin whatever the money says."""
    line = advice_line(record(), _ranking_saving(Option.repair, 0), blocked=True)
    assert line == "Repair it, not trash"


def test_the_threshold_is_a_setting() -> None:
    saving = _ranking_saving(Option.resell, 250)
    assert advice_line(record(), saving, blocked=False, speak_up_cents=100) == (
        "Resell it, not trash"
    )
    assert advice_line(record(), saving, blocked=False, speak_up_cents=500) == FINE_TO_BIN


def test_the_bin_winning_outright_is_fine_to_bin_too() -> None:
    assert advice_line(record(), _ranking_saving(Option.trash, 0), blocked=False) == (
        FINE_TO_BIN
    )
    assert advice_line(record(), _ranking_saving(None, 0), blocked=False) == FINE_TO_BIN


def test_every_line_the_bin_can_draw_still_fits() -> None:
    assert len(FINE_TO_BIN) <= 20
