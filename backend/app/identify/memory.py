"""Exemplar memory: the free, local half of identification.

PLAN.md section 9 item 2. Every confirmed answer leaves an exemplar behind, so the second
time the same thing is tossed the crop is recognised from the table with no cloud call.
The index is a plain matrix held in memory and kept in step with the exemplar table, which
is the right shape for a few thousand rows and needs no extra dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.identify.embed import from_bytes
from app.models import Exemplar

DEFAULT_K = 5
# 4 of 5 in PLAN.md section 9. Below five neighbours the same share is required, rounded up,
# so three neighbours need three and two need two. One neighbour may carry itself, and the
# distance gate still has to pass.
VOTE_SHARE = 0.8


@dataclass(frozen=True)
class Neighbour:
    label: str
    distance: float
    exemplar_id: int


@dataclass(frozen=True)
class MemoryHit:
    label: str
    distance: float
    votes: int
    considered: int
    neighbours: tuple[Neighbour, ...]

    @property
    def confidence(self) -> float:
        """How much of the neighbourhood agreed. The accept rule keeps this at 0.8 or above."""
        return self.votes / self.considered if self.considered else 0.0


def votes_needed(considered: int) -> int:
    """The 4 of 5 rule, scaled to however many neighbours the table actually holds."""
    if considered <= 0:
        return 0
    return max(1, math.ceil(VOTE_SHARE * considered))


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

    def decide(self, neighbours: list[Neighbour], settings: Settings) -> MemoryHit | None:
        """Accept when the neighbourhood agrees and the nearest match is genuinely close."""
        if not neighbours:
            return None
        counts: dict[str, int] = {}
        for neighbour in neighbours:
            counts[neighbour.label] = counts.get(neighbour.label, 0) + 1
        label = max(counts, key=lambda name: (counts[name], -_first_distance(neighbours, name)))
        votes = counts[label]
        nearest = min(n.distance for n in neighbours if n.label == label)
        if votes < votes_needed(len(neighbours)):
            return None
        if nearest > settings.memory_max_dist:
            return None
        return MemoryHit(
            label=label,
            distance=nearest,
            votes=votes,
            considered=len(neighbours),
            neighbours=tuple(neighbours),
        )


def _first_distance(neighbours: list[Neighbour], label: str) -> float:
    return min(n.distance for n in neighbours if n.label == label)


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
