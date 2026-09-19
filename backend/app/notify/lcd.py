"""Builders for every LCD screen.

PLAN.md section 6: the firmware draws two text lines of at most 20 characters, one big string
of at most 7, and a background colour. Truncation is the backend's job. It happens inside the
LcdLine and LcdBig types in schemas.py, so every builder here is a thin, named wrapper and no
route can bypass the cut by building a screen by hand.
"""

from __future__ import annotations

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


__all__ = [
    "LCD_BIG_MAX",
    "LCD_LINE_MAX",
    "ScreenAsk",
    "ScreenIdle",
    "ScreenOffline",
    "ScreenResult",
    "ScreenThinking",
    "ask",
    "fit_big",
    "fit_line",
    "idle",
    "offline",
    "result",
    "thinking",
]
