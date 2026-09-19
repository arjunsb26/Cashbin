"""The one rule that decides whether the local-first path ever engages.

PLAN.md section 9 item 2 accepts a remembered answer when the top label holds at least four
of five neighbours. PLAN.md section 20 M2 says tossing the same item again resolves from
memory for nothing. Those two only agree while the exemplar table holds fewer than five
rows: after that, a perfect match sits alone among four unrelated neighbours, the vote fails
and the same crop is sent to the model again.

That is what the M4 soak measured. A label needed four confirmed exemplars before memory
would answer it, so over sixty tosses the local share reached 0.17 and the cost per event
barely moved. The fix here is the smallest one that makes both PLAN sections true: a
neighbour that is all but the same picture is accepted on its own, and everything else still
has to win the vote.
"""

from __future__ import annotations

from app.config import Settings
from app.identify.memory import MemoryIndex, Neighbour, votes_needed

SETTINGS = Settings(_env_file=None)


def neighbours(*pairs: tuple[str, float]) -> list[Neighbour]:
    return [
        Neighbour(label=label, distance=distance, exemplar_id=index + 1)
        for index, (label, distance) in enumerate(pairs)
    ]


def test_an_all_but_identical_crop_is_accepted_on_its_own() -> None:
    """One exemplar, four strangers, and the one is the same picture. That is a match."""
    index = MemoryIndex()
    found = index.decide(
        neighbours(
            ("bike light", 0.0),
            ("banana", 0.41),
            ("cookie", 0.44),
            ("mouse", 0.52),
            ("phone", 0.61),
        ),
        SETTINGS,
    )
    assert found is not None
    assert found.label == "bike light"
    assert found.votes == 1


def test_a_merely_close_neighbour_still_has_to_win_the_vote() -> None:
    """Close is not the same. A single vote at an ordinary distance is still a no."""
    index = MemoryIndex()
    assert (
        index.decide(
            neighbours(
                ("bike light", 0.30),
                ("banana", 0.31),
                ("cookie", 0.33),
                ("mouse", 0.34),
                ("phone", 0.34),
            ),
            SETTINGS,
        )
        is None
    )


def test_the_vote_still_carries_a_label_with_four_of_five() -> None:
    index = MemoryIndex()
    found = index.decide(
        neighbours(
            ("banana", 0.20),
            ("banana", 0.21),
            ("banana", 0.22),
            ("banana", 0.23),
            ("cookie", 0.24),
        ),
        SETTINGS,
    )
    assert found is not None
    assert found.label == "banana"
    assert found.votes == 4
    assert votes_needed(5) == 4


def test_an_identical_crop_that_is_too_far_to_be_believed_is_still_refused() -> None:
    """The distance gate is the wall. Nothing gets in past `memory_max_dist`."""
    index = MemoryIndex()
    far = SETTINGS.model_copy(update={"memory_max_dist": 0.001})
    assert index.decide(neighbours(("bike light", 0.2)), far) is None


def test_a_photograph_of_the_same_thing_is_not_the_same_photograph() -> None:
    """The single vote rule is for the same picture only, and 0.05 is not the same picture."""
    index = MemoryIndex()
    assert (
        index.decide(
            neighbours(
                ("bike light", 0.05),
                ("banana", 0.30),
                ("cookie", 0.32),
                ("mouse", 0.33),
                ("phone", 0.34),
            ),
            SETTINGS,
        )
        is None
    )
