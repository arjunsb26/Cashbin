"""What memory is allowed to do, now that it is not allowed to answer.

PLAN.md 21a item 23. Lane K measured the embedder on 39 real photographs: two pictures of
the same object are further apart than the two closest pictures of different objects, so no
value of `memory_max_dist` separates them. In a thirty toss run memory fired twice and was
wrong both times, posting an HDMI cable to the books as a USB-C charger in 84 ms for
nothing.

So the model is always asked, and memory is a second opinion on what it said. These tests
are the wall around that: a lone exemplar cannot finalise anything, and agreement makes an
unsure answer sure rather than replacing it.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from app.config import Settings
from app.identify.memory import MemoryIndex, Neighbour, boost, boost_label

SETTINGS = Settings(_env_file=None)


def neighbours(*pairs: tuple[str, float]) -> list[Neighbour]:
    return [
        Neighbour(label=label, distance=distance, exemplar_id=index + 1)
        for index, (label, distance) in enumerate(pairs)
    ]


def test_a_lone_exemplar_of_a_different_object_cannot_finalise_a_toss() -> None:
    """Lane K section 5, tosses 16 and 22: one usb-c charger exemplar 0.2097 from an HDMI
    cable, inside the 0.35 gate, answering for it twice at zero cost with `is_final` set."""
    index = MemoryIndex()
    found = index.agreement(neighbours(("usb-c charger", 0.2097)), "hdmi cable", SETTINGS)
    assert found.agrees is False
    assert [n.label for n in found.disagreeing] == ["usb-c charger"]
    # And it cannot reach the answer either, because it is not the answer's label.
    unchanged = boost_label({"hdmi cable": 0.78, "usb cable": 0.20}, "hdmi cable", 0)
    assert unchanged == {"hdmi cable": 0.78, "usb cable": 0.20}


def test_an_all_but_identical_crop_cannot_answer_on_its_own_either() -> None:
    """The old rule accepted a neighbour this close without a vote. There is no such rule
    now: memory has no way to produce an answer at all, however close the crop is."""
    index = MemoryIndex()
    assert not hasattr(index, "decide")
    found = index.agreement(neighbours(("bike light", 0.0)), "banana", SETTINGS)
    assert found.agrees is False


def test_agreement_turns_an_unsure_answer_into_a_sure_one() -> None:
    """This is what replaces the free answer: the ask stops being asked as it learns."""
    sure_enough = SETTINGS.confident_p
    first_time = 0.70
    assert first_time < sure_enough
    assert boost(first_time, 1) >= sure_enough
    raised = boost_label({"bike light": first_time, "mouse": 0.20}, "bike light", 1)
    assert raised["bike light"] >= sure_enough
    assert raised["bike light"] - raised["mouse"] >= SETTINGS.min_margin


def test_an_exemplar_past_the_distance_gate_counts_for_nothing() -> None:
    far = SETTINGS.memory_max_dist + 0.01
    found = MemoryIndex().agreement(neighbours(("bike light", far)), "bike light", SETTINGS)
    assert found.agrees is False
    assert found.nearest is None


def test_more_examples_help_less_and_never_reach_certainty() -> None:
    steps = [boost(0.5, n) for n in range(1, 6)]
    gains = [b - a for a, b in pairwise(steps)]
    assert gains == sorted(gains, reverse=True)
    assert max(steps) < 1.0
    assert boost(0.5, 100) == pytest.approx(0.99)
