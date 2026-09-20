"""Exemplar memory: who the neighbours are, and how much they are allowed to say."""

from __future__ import annotations

import numpy as np
import pytest

from app.config import Settings
from app.db import session_scope
from app.identify.embed import to_bytes
from app.identify.memory import MemoryIndex, Neighbour, boost, boost_label
from app.models import Exemplar
from tests.test_identify_support import make_event, setup_db


def unit(*values: float) -> np.ndarray:
    vector = np.array(values, dtype=np.float32)
    return vector / float(np.linalg.norm(vector))


def index_with(labels: list[tuple[str, np.ndarray]]) -> MemoryIndex:
    index = MemoryIndex()
    for number, (label, vector) in enumerate(labels, start=1):
        index.add(Exemplar(id=number, event_id=number, label=label, embedding=to_bytes(vector)))
    return index


def neighbours(*pairs: tuple[str, float]) -> list[Neighbour]:
    return [
        Neighbour(label=label, distance=distance, exemplar_id=i)
        for i, (label, distance) in enumerate(pairs, start=1)
    ]


def test_query_returns_the_nearest_first(settings: Settings) -> None:
    index = index_with([("bagel", unit(1, 0, 0)), ("cookie", unit(0, 1, 0))])
    found = index.query(unit(1, 0.1, 0), k=2)
    assert [n.label for n in found] == ["bagel", "cookie"]
    assert found[0].distance < found[1].distance


def test_neighbours_that_back_the_answer_are_told_apart_from_the_ones_that_do_not(
    settings: Settings,
) -> None:
    found = MemoryIndex().agreement(
        neighbours(("bagel", 0.02), ("bagel", 0.05), ("cookie", 0.10)), "bagel", settings
    )
    assert found.agrees is True
    assert len(found.agreeing) == 2
    assert [n.label for n in found.disagreeing] == ["cookie"]
    assert found.nearest == pytest.approx(0.02)


def test_a_neighbour_past_the_distance_gate_counts_for_neither_side(
    settings: Settings,
) -> None:
    far = settings.memory_max_dist + 0.05
    found = MemoryIndex().agreement(
        neighbours(("bagel", far), ("cookie", far)), "bagel", settings
    )
    assert found.agrees is False
    assert found.disagreeing == ()


def test_memory_disagreeing_changes_nothing(settings: Settings) -> None:
    """Lane K section 5: the only two answers memory ever gave were wrong ones."""
    found = MemoryIndex().agreement(
        neighbours(("usb-c charger", 0.21)), "hdmi cable", settings
    )
    assert found.agrees is False
    assert [n.label for n in found.disagreeing] == ["usb-c charger"]


def test_each_agreeing_example_halves_the_doubt() -> None:
    assert boost(0.70, 0) == pytest.approx(0.70)
    assert boost(0.70, 1) == pytest.approx(0.85)
    assert boost(0.70, 2) == pytest.approx(0.925)
    # Never certain, however many examples agree.
    assert boost(0.70, 40) == pytest.approx(0.99)


def test_the_boost_takes_what_it_gains_from_the_other_labels() -> None:
    raised = boost_label({"bagel": 0.60, "cookie": 0.30}, "bagel", 1)
    assert raised["bagel"] == pytest.approx(0.80)
    assert raised["cookie"] == pytest.approx(0.10)
    # The share the model left unspoken for is untouched.
    assert sum(raised.values()) == pytest.approx(0.90)


def test_a_label_memory_never_saw_is_left_alone() -> None:
    same = {"bagel": 0.60, "cookie": 0.30}
    assert boost_label(same, "phone", 3) == same
    assert boost_label(same, "bagel", 0) == same


def test_an_empty_neighbourhood_agrees_with_nothing(settings: Settings) -> None:
    found = MemoryIndex().agreement([], "bagel", settings)
    assert found.agrees is False
    assert MemoryIndex().query(unit(1, 0, 0)) == []


def test_the_index_loads_from_the_table_and_stays_in_step(settings: Settings) -> None:
    setup_db(settings)
    index = MemoryIndex()
    with session_scope() as session:
        event = make_event(session)
        session.add(
            Exemplar(event_id=event.id, label="bagel", embedding=to_bytes(unit(1, 0, 0)))
        )
        session.flush()
        index.load(session)
        assert len(index) == 1 and index.loaded

        second = Exemplar(event_id=event.id, label="cookie", embedding=to_bytes(unit(0, 1, 0)))
        session.add(second)
        session.flush()
        index.add(second)
    assert len(index) == 2
    assert [n.label for n in index.query(unit(0, 1, 0), k=1)] == ["cookie"]


def test_a_probe_of_the_wrong_width_is_refused(settings: Settings) -> None:
    index = index_with([("bagel", unit(1, 0, 0))])
    with pytest.raises(ValueError, match="width"):
        index.query(unit(1, 0))
