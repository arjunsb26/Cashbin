"""Builders for every LCD screen.

PLAN.md section 6: the firmware draws two text lines of at most 20 characters, one big string
of at most 7, and a background colour. Truncation is the backend's job. It happens inside the
LcdLine and LcdBig types in schemas.py, so every builder here is a thin, named wrapper and no
route can bypass the cut by building a screen by hand.
"""

from __future__ import annotations

from app.engine.records import ItemClass
from app.engine.tax import money
from app.schemas import (
    LCD_BIG_MAX,
    LCD_LINE_MAX,
    LcdColour,
    ScreenAsk,
    ScreenIdle,
    ScreenOffline,
    ScreenResult,
    ScreenThinking,
    lcd_text,
)


def fit_line(text: str) -> str:
    """What the bin will actually draw for a text line."""
    return str(lcd_text(text, LCD_LINE_MAX))


def fit_big(text: str) -> str:
    """What the bin will actually draw for the big figure. Spaces are dropped first."""
    return str(lcd_text(text, LCD_LINE_MAX)).replace(" ", "")[:LCD_BIG_MAX]


def idle() -> ScreenIdle:
    return ScreenIdle()


def thinking() -> ScreenThinking:
    return ScreenThinking()


def offline() -> ScreenOffline:
    return ScreenOffline()


def result(line1: str, big: str, line2: str, colour: LcdColour) -> ScreenResult:
    """The result screen. DESIGN.md section 7 draws line 1 at the top, big centred, line 2 below."""
    return ScreenResult(l1=line1, big=big, l2=line2, c=colour)


def ask(line1: str = "Not sure", line2: str = "Check the dashboard") -> ScreenAsk:
    """The ask screen. The wording is the one in PLAN.md section 6."""
    return ScreenAsk(l1=line1, l2=line2)


# What a toss means, in the two words the bin has room for -------------------
#
# PLAN.md 21a item 41. The figure alone says nothing: minus four dollars on a bagel and
# minus four dollars on a laptop are different events, and the word above the figure is
# what tells them apart. Food is wasted, a tracked asset is written off, anything else is
# worth what somebody would pay for it, and packaging is carbon nobody had to emit.

PACKAGING = "packaging"
HEADLINES: dict[ItemClass, str] = {
    ItemClass.inventory: "Wasted",
    ItemClass.fixed_asset: "Written off",
    ItemClass.untracked: "Worth about",
}
CARBON_HEADLINE = "CO2e avoided"
IDLE_HEADLINE = "In the bin"
IDLE_EMPTY = "Nothing in it yet"


def big_money(cents: int) -> str:
    """A figure in cents, cut down until the bin can draw it. Cents go first, then commas.

    Seven characters is the whole budget, so "$1,234.56" cannot be drawn and "$1,234" can.
    Past six figures it rounds to thousands, and the exact figure is on the ticket.
    """
    sign = "-" if cents < 0 else ""
    full = f"{sign}${money(abs(cents))}"
    if len(full) <= LCD_BIG_MAX:
        return full
    whole = f"{sign}${abs(cents) // 100:,}"
    if len(whole) <= LCD_BIG_MAX:
        return whole
    plain = whole.replace(",", "")
    if len(plain) <= LCD_BIG_MAX:
        return plain
    return f"{sign}${round(abs(cents) / 100_000)}k"


def big_grams(grams: float) -> str:
    """A weight the bin can draw. Grams while they fit, then kilograms, then tonnes."""
    rounded = round(grams)
    kilos = rounded / 1000
    for candidate in (f"{rounded:,}g", f"{kilos:,.1f}kg", f"{round(kilos):,}kg",
                      f"{round(kilos / 1000):,}t"):
        if len(candidate) <= LCD_BIG_MAX:
            return candidate
    return f"{round(kilos / 1000)}t"[:LCD_BIG_MAX]


def headline_for(item_class: ItemClass, cents: int, kind: str = "") -> tuple[str, str]:
    """Line 1 and the big figure for one toss, as its class decides.

    `cents` is the size of what happened, without a sign: the word above it already says
    whether it was lost or gained, and a minus sign on the LCD reads as a fault. Packaging
    is the exception: `kind` is "packaging", the figure is grams of CO2e, and the screen
    leads with the carbon rather than with money nobody spent.
    """
    if kind == PACKAGING:
        return fit_line(CARBON_HEADLINE), fit_big(big_grams(abs(cents)))
    return fit_line(HEADLINES[item_class]), fit_big(big_money(abs(cents)))


def idle_screen(total_cents: int, weight_g: float, count: int) -> ScreenResult:
    """What the bin shows between tosses: what is in it since the last bag change.

    PLAN.md 21a item 45. The user asked for the value of what is inside to update live, so
    the resting screen is the running total rather than a logo. An empty bin says what
    would fill it instead of drawing a row of zeroes.
    """
    if count <= 0:
        return result(IDLE_HEADLINE, fit_big(big_money(0)), IDLE_EMPTY, "neutral")
    items = "1 item" if count == 1 else f"{count:,} items"
    grams = f"{round(weight_g):,} g"
    return result(IDLE_HEADLINE, fit_big(big_money(abs(total_cents))),
                  f"{grams}, {items}", "neutral")


__all__ = [
    "CARBON_HEADLINE",
    "HEADLINES",
    "IDLE_EMPTY",
    "IDLE_HEADLINE",
    "LCD_BIG_MAX",
    "LCD_LINE_MAX",
    "PACKAGING",
    "ScreenAsk",
    "ScreenIdle",
    "ScreenOffline",
    "ScreenResult",
    "ScreenThinking",
    "ask",
    "big_grams",
    "big_money",
    "fit_big",
    "fit_line",
    "headline_for",
    "idle",
    "idle_screen",
    "offline",
    "result",
    "thinking",
]
