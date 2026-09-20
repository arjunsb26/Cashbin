"""Exemplar memory: the part of identification that says "I have seen this before".

PLAN.md 21a item 23. Memory used to answer on its own and skip the model. Lane K measured
what that does to real photographs: the two photographs of the same object are further
apart than the two closest photographs of different objects, so no threshold separates
them, and in a thirty toss run memory fired twice and was wrong both times, posting an HDMI
cable to the books as a USB-C charger in 84 ms for nothing. A free, instant, confident,
wrong answer is worse than a slow right one.

So memory no longer decides. The model is always asked, and memory is a second opinion on
the answer: neighbours that agree with it raise the confidence, so asks fall as the system
learns, and neighbours that disagree are logged and change nothing.

The index is a plain matrix held in memory and kept in step with the exemplar table, which
is the right shape for a few thousand rows and needs no extra dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.identify.embed import from_bytes
from app.models import Exemplar

DEFAULT_K = 5
# Each neighbour that agrees with the model halves the doubt left in its answer. Two
# agreeing exemplars take a 0.70 answer to 0.925, which is how an ask stops being asked
# once a person has confirmed the same thing a couple of times.
AGREEMENT_HALVING = 0.5
# Never exactly certain. Nothing a histogram says should make an answer unquestionable.
MAX_BOOSTED_P = 0.99


@dataclass(frozen=True)
class Neighbour:
    label: str
    distance: float
    exemplar_id: int


@dataclass(frozen=True)
class Agreement:
    """What memory thinks of the answer the model just gave."""

    label: str
    agreeing: tuple[Neighbour, ...]
    disagreeing: tuple[Neighbour, ...]

    @property
    def agrees(self) -> bool:
        return bool(self.agreeing)

    @property
    def nearest(self) -> float | None:
        return min((n.distance for n in self.agreeing), default=None)


def boost(p: float, agreeing: int, cap: float = MAX_BOOSTED_P) -> float:
    """Raise a probability toward certainty, once per neighbour that agrees.

    Each agreeing exemplar halves what is left of the doubt, so the first one counts for
    most and the tenth counts for almost nothing. Capped, because a colour histogram is not
    proof.
    """
    if agreeing <= 0:
        return p
    return min(cap, 1.0 - (1.0 - p) * (AGREEMENT_HALVING**agreeing))


def boost_label(
    distribution: dict[str, float], label: str, agreeing: int, cap: float = MAX_BOOSTED_P
) -> dict[str, float]:
    """The same distribution with one label more believed and the rest less.

    What the boost takes it takes from the other labels, so the share the model left
    unspoken for is untouched. An answer nobody can name stays just as unnamed.
    """
    if agreeing <= 0 or label not in distribution:
        return dict(distribution)
    raised = boost(distribution[label], agreeing, cap)
    gain = raised - distribution[label]
    if gain <= 0.0:
        return dict(distribution)
    others = {name: p for name, p in distribution.items() if name != label}
    pool = sum(others.values())
    out = {label: raised}
    scale = max(0.0, (pool - gain) / pool) if pool > 0.0 else 0.0
    for name, p in others.items():
        out[name] = p * scale
    return out


class MemoryIndex:
    """kNN over exemplar embeddings, cosine distance, loaded once and updated as rows arrive."""

    def __init__(self) -> None:
        self._vectors: list[NDArray[np.float32]] = []
        self._labels: list[str] = []
        self._ids: list[int] = []
        self.loaded = False

    def __len__(self) -> int:
        return len(self._ids)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(self._labels)

    def load(self, session: Session) -> MemoryIndex:
        """Replace the index with everything in the exemplar table."""
        self._vectors = []
        self._labels = []
        self._ids = []
        for row in session.execute(select(Exemplar).order_by(Exemplar.id)).scalars():
            self.add(row)
        self.loaded = True
        return self

    def ensure_loaded(self, session: Session) -> MemoryIndex:
        """Read the table once per process. `add` keeps it in step after that."""
        return self if self.loaded else self.load(session)

    def add(self, exemplar: Exemplar) -> None:
        """Keep the index in step with the table, so a new answer counts on the next toss."""
        vector = from_bytes(exemplar.embedding)
        if vector.size == 0:
            return
        self._vectors.append(vector)
        self._labels.append(exemplar.label)
        self._ids.append(exemplar.id)

    def query(self, vector: NDArray[np.float32], k: int = DEFAULT_K) -> list[Neighbour]:
        """The k nearest exemplars by cosine distance, nearest first."""
        if not self._vectors or k <= 0:
            return []
        matrix = np.vstack(self._vectors)
        probe = np.asarray(vector, dtype=np.float32)
        if probe.shape[0] != matrix.shape[1]:
            raise ValueError("embedding width does not match the index")
        distances = 1.0 - matrix @ probe
        order = np.argsort(distances, kind="stable")[:k]
        return [
            Neighbour(
                label=self._labels[int(i)],
                distance=float(distances[int(i)]),
                exemplar_id=self._ids[int(i)],
            )
            for i in order
        ]

    def agreement(
        self, neighbours: list[Neighbour], label: str, settings: Settings
    ) -> Agreement:
        """Split the neighbourhood into the ones that back this label and the ones that do not.

        Only neighbours inside `memory_max_dist` count either way. Anything further away is
        not a neighbour, it is just the nearest row in a small table.
        """
        near = [n for n in neighbours if n.distance <= settings.memory_max_dist]
        return Agreement(
            label=label,
            agreeing=tuple(n for n in near if n.label == label),
            disagreeing=tuple(n for n in near if n.label != label),
        )


_index: MemoryIndex | None = None


def get_memory() -> MemoryIndex:
    """The process-wide index. Load it from a session before the first query."""
    global _index
    if _index is None:
        _index = MemoryIndex()
    return _index


def reset_memory() -> MemoryIndex:
    """Drop the index. Tests call this between cases, as does a database swap."""
    global _index
    _index = MemoryIndex()
    return _index
