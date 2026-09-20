"""Clean money. PLAN.md 21a item 47: an estimate reads like a price, not like a reading.

The user's words are "THE ESTIMATES NEED TO BE CLEAN AS FUCK". A model answers 1173 cents
because it averaged two listings, and 11 dollars 73 on a screen reads as a measurement
somebody took. The bands here are the ones in item 47, in cents.
"""

from __future__ import annotations

import pytest

from app.identify.rounding import BANDS, round_money


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The four in the brief.
        (1173, 1200),
        (9987, 10000),
        (12345, 12500),
        (137, 150),
        # Nothing is nothing, and a figure already on a step stays where it is.
        (0, 0),
        (150, 150),
        (1200, 1200),
        (10000, 10000),
        (12500, 12500),
        (100000, 100000),
        # Every band, at its bottom and at its top.
        (1, 50),
        (1999, 2000),
        (2000, 2000),
        (2001, 2100),
        (9999, 10000),
        (10001, 10500),
        (99999, 100000),
        (100001, 101000),
        (1234567, 1235000),
    ],
)
def test_round_money_lands_on_its_band_step(raw: int, expected: int) -> None:
    assert round_money(raw) == expected


def test_a_rounded_figure_is_never_lower_than_the_model_said() -> None:
    """Rounding up, not to the nearest, so "about 12 dollars" never reads under the range."""
    for cents in range(0, 3000, 7):
        assert round_money(cents) >= cents


def test_rounding_is_idempotent() -> None:
    for cents in (0, 137, 1173, 9987, 12345, 99999, 1234567):
        assert round_money(round_money(cents)) == round_money(cents)


def test_a_negative_figure_rounds_away_from_zero_on_its_size() -> None:
    """Nothing sends one today, and a loss that reads smaller than it is would be a lie."""
    assert round_money(-1173) == -1200
    assert round_money(-137) == -150


def test_the_bands_are_the_ones_the_plan_names() -> None:
    assert BANDS == ((2000, 50), (10000, 100), (100000, 500))
