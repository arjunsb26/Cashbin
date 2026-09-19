"""Exemplar memory: who the neighbours are, and when their vote is enough."""

from __future__ import annotations

import numpy as np
import pytest

from app.config import Settings
from app.db import session_scope
from app.identify.embed import to_bytes
from app.identify.memory import MemoryIndex, Neighbour, votes_needed
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


def test_the_vote_rule_scales_to_a_small_table() -> None:
    # 4 of 5 in PLAN.md section 9, and the same share rounded up below five neighbours.
    assert [votes_needed(n) for n in (0, 1, 2, 3, 4, 5)] == [0, 1, 2, 3, 4, 4]


def test_query_returns_the_nearest_first(settings: Settings) -> None:
    index = index_with([("bagel", unit(1, 0, 0)), ("cookie", unit(0, 1, 0))])
    found = index.query(unit(1, 0.1, 0), k=2)
    assert [n.label for n in found] == ["bagel", "cookie"]
    assert found[0].distance < found[1].distance


def test_a_clear_neighbourhood_is_accepted(settings: Settings) -> None:
    index = MemoryIndex()
    hit = index.decide(
        neighbours(
            ("bagel", 0.02), ("bagel", 0.05), ("bagel", 0.08), ("bagel", 0.1), ("cookie", 0.3)
        ),
        settings,
    )
    assert hit is not None
    assert hit.label == "bagel"
    assert hit.votes == 4
    assert hit.confidence == pytest.approx(0.8)


def test_a_split_neighbourhood_is_refused(settings: Settings) -> None:
    hit = MemoryIndex().decide(
        neighbours(
            ("bagel", 0.02), ("bagel", 0.05), ("bagel", 0.08), ("cookie", 0.1), ("cookie", 0.12)
        ),
        settings,
    )
    assert hit is None


def test_a_distant_match_is_refused_however_well_it_votes(settings: Settings) -> None:
    far = settings.memory_max_dist + 0.05
    hit = MemoryIndex().decide(
        neighbours(("bagel", far), ("bagel", far), ("bagel", far), ("bagel", far)), settings
    )
    assert hit is None


def test_one_neighbour_may_carry_itself_when_it_is_close(settings: Settings) -> None:
    hit = MemoryIndex().decide(neighbours(("bagel", 0.01)), settings)
    assert hit is not None and hit.label == "bagel" and hit.considered == 1


def test_three_neighbours_need_all_three(settings: Settings) -> None:
    assert MemoryIndex().decide(
        neighbours(("bagel", 0.01), ("bagel", 0.02), ("cookie", 0.03)), settings
    ) is None
    assert MemoryIndex().decide(
        neighbours(("bagel", 0.01), ("bagel", 0.02), ("bagel", 0.03)), settings
    ) is not None


def test_an_empty_neighbourhood_decides_nothing(settings: Settings) -> None:
    assert MemoryIndex().decide([], settings) is None
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
