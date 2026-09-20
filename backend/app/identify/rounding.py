"""Money a person can read, from a number a model happened to say.

PLAN.md 21a item 47. A model prices a used mouse at 1173 cents because it averaged two
listings, and 11 dollars 73 on the LCD reads as a measurement somebody took rather than an
estimate somebody made. The bands below are the plan's own: 50 cents under 20 dollars, a
dollar up to 100, 5 dollars up to 1000, 10 dollars above that.

Two decisions worth knowing. It rounds up rather than to the nearest, so a cleaned figure
never reads lower than what the estimator actually said, which is the safe direction for a
write off and for advice to sell something. And only the mid of a range is cleaned; the low
and the high stay raw, so the drawer still shows the spread the model gave.
"""

from __future__ import annotations

# (below this many cents, round up to a multiple of this many cents). Anything at or above
# the last limit uses STEP_ABOVE.
BANDS: tuple[tuple[int, int], ...] = ((2000, 50), (10000, 100), (100000, 500))
STEP_ABOVE = 1000


def step_for(cents: int) -> int:
    """The step one figure is cleaned to. Chosen on the raw figure, never on the result."""
    size = abs(cents)
    for limit, step in BANDS:
        if size < limit:
            return step
    return STEP_ABOVE


def round_money(cents: int) -> int:
    """One figure in cents, cleaned to its band's step, away from zero."""
    step = step_for(cents)
    size = abs(int(cents))
    up = -(-size // step) * step
    return -up if cents < 0 else up


__all__ = ["BANDS", "STEP_ABOVE", "round_money", "step_for"]
