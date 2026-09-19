"""Builders for every LCD screen, with the truncation the firmware relies on.

PLAN.md section 6: the firmware draws two text lines of at most 20 characters, one big string
of at most 7, and a background colour. Truncation is the backend's job, so it happens here and
nowhere else. Every builder returns a validated model, so an over-long string cannot reach the bin.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas import (
    LCD_BIG_MAX,
    LCD_LINE_MAX,
    LcdColour,
    ScreenAsk,
    ScreenIdle,
    ScreenOffline,
    ScreenResult,
    ScreenThinking,
)

_WHITESPACE = re.compile(r"\s+")

# The LCD font has no glyph for anything outside plain ASCII, so fold first, then drop.
_ELLIPSIS = "…"


def _flatten(text: str) -> str:
    """One line of plain ASCII. Accents fold, everything else that cannot fold is dropped."""
    folded = unicodedata.normalize("NFKD", text)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    return _WHITESPACE.sub(" ", ascii_only).strip()


def fit_line(text: str, limit: int = LCD_LINE_MAX) -> str:
    """Cut a text line to the limit. A cut line ends in a full stop so it reads as cut."""
    flat = _flatten(text)
    if len(flat) <= limit:
        return flat
    if limit <= 1:
        return flat[:limit]
    return flat[: limit - 1].rstrip() + "."


def fit_big(text: str, limit: int = LCD_BIG_MAX) -> str:
    """Cut the big figure. Money keeps its sign and its leading digits, never its tail."""
    flat = _flatten(text).replace(" ", "")
    if len(flat) <= limit:
        return flat
    return flat[:limit]


def idle() -> ScreenIdle:
    return ScreenIdle()


def thinking() -> ScreenThinking:
    return ScreenThinking()


def offline() -> ScreenOffline:
    return ScreenOffline()


def result(line1: str, big: str, line2: str, colour: LcdColour) -> ScreenResult:
    """The result screen. DESIGN.md section 7 draws line 1 at the top, big centred, line 2 below."""
    return ScreenResult(l1=fit_line(line1), big=fit_big(big), l2=fit_line(line2), c=colour)


def ask(line1: str = "Not sure", line2: str = "Check the dashboard") -> ScreenAsk:
    """The ask screen. The wording is the one in PLAN.md section 6."""
    return ScreenAsk(l1=fit_line(line1), l2=fit_line(line2))


__all__ = [
    "LCD_BIG_MAX",
    "LCD_LINE_MAX",
    "ask",
    "fit_big",
    "fit_line",
    "idle",
    "offline",
    "result",
    "thinking",
]
