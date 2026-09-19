"""Draw the 240x320 LCD as a text box, so the LCD is readable in a terminal log.

DESIGN.md section 7 is the layout this mimics: line 1 at the top, the big figure
centred, line 2 at the bottom, and the tone colour filling the screen. The colour
cannot be drawn in a log, so it is named under the box.

Pure string work. `sim/bin_sim.py` prints every `screen` message through here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

INNER = 24
LINE_MAX = 20
BIG_MAX = 7
TONES = ("green", "amber", "red", "neutral")


def format_weight(grams: float) -> str:
    """The idle and thinking screens show the current weight as the big figure."""
    whole = round(grams)
    wide = f"{whole:,} g"
    return wide if len(wide) <= BIG_MAX else f"{whole} g"[:BIG_MAX]


def screen_lines(
    msg: Mapping[str, Any],
    weight_g: float | None = None,
) -> tuple[str, str, str, str]:
    """Turn a `screen` message into line 1, the big figure, line 2 and the tone.

    The backend owns truncation. This truncates again so a bad message cannot break
    the box, which is the same rule the firmware follows.
    """
    state = str(msg.get("s", "idle"))
    line1 = str(msg.get("l1", ""))
    line2 = str(msg.get("l2", ""))
    big = str(msg.get("big", ""))
    tone = str(msg.get("c", "neutral"))

    if state == "idle" and not any((line1, line2, big)):
        big = format_weight(weight_g) if weight_g is not None else ""
    elif state == "thinking":
        line1 = line1 or "Weighing"
        big = big or (format_weight(weight_g) if weight_g is not None else "")
    elif state == "offline":
        line1 = line1 or "Offline"
        line2 = line2 or "No connection"

    if tone not in TONES:
        tone = "neutral"
    return line1[:LINE_MAX], big[:BIG_MAX], line2[:LINE_MAX], tone


def render_screen(msg: Mapping[str, Any], weight_g: float | None = None) -> str:
    """Render one `screen` message as the box plus the tone name."""
    line1, big, line2, tone = screen_lines(msg, weight_g)
    edge = "+" + "-" * INNER + "+"
    rows = [
        edge,
        _left(line1),
        _blank(),
        _centre(big),
        _blank(),
        _left(line2),
        edge,
        f"  {tone}",
    ]
    return "\n".join(rows)


def _blank() -> str:
    return "|" + " " * INNER + "|"


def _left(text: str) -> str:
    body = f"  {text}".ljust(INNER)[:INNER]
    return f"|{body}|"


def _centre(text: str) -> str:
    return f"|{text.center(INNER)[:INNER]}|"
