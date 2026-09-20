"""The deterministic providers. No key, no network, no cost.

PLAN.md rule 1: the whole system runs on a laptop with no bin, no phone and no internet.
These two providers are what makes that true, and they are also what every test uses, so
the identification path under test is the same path the demo runs.

The vision stub answers, in order:

1. the label the simulator said was coming, through POST /api/sim/expect,
2. otherwise the catalog label whose SHA-1 sits closest to the crop's SHA-1.

Either way the answer is confident when the label is in the catalog and unsure when it is
not, so the ask path is exercised without anybody having to break something first.
"""

from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass

from app.identify.providers import CallUsage, IdentifyContext
from app.models import ItemClass
from app.schemas import (
    MoneyRange,
    ValueEstimate,
    VisionCandidate,
    VisionResult,
    normalise_label,
)

STUB_NAME = "stub"
CONFIDENT_P = 0.95
UNSURE_P = 0.55
FALLBACK_LABEL = "unknown object"


@dataclass(frozen=True)
class Expectation:
    """One queued answer from the simulator."""

    label: str
    mass_g: float | None = None


class ExpectQueue:
    """What the simulator says is coming next. Dev only, fed by POST /api/sim/expect."""

    def __init__(self) -> None:
        self._items: deque[Expectation] = deque()

    def push(self, label: str, mass_g: float | None = None) -> Expectation:
        item = Expectation(label=normalise_label(label), mass_g=mass_g)
        self._items.append(item)
        return item

    def pop(self) -> Expectation | None:
        return self._items.popleft() if self._items else None

    def peek(self) -> Expectation | None:
        return self._items[0] if self._items else None

    def pending(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()


_queue: ExpectQueue | None = None


def get_expect_queue() -> ExpectQueue:
    global _queue
    if _queue is None:
        _queue = ExpectQueue()
    return _queue


def reset_expect_queue() -> ExpectQueue:
    """Tests and a fresh run start with nothing queued."""
    global _queue
    _queue = ExpectQueue()
    return _queue


def _catalog_labels() -> tuple[str, ...]:
    """Catalog labels from the seed file. An absent file means an empty catalog, not a crash."""
    try:
        from app.engine.records import load_catalog

        return tuple(item.label for item in load_catalog())
    except (OSError, KeyError, ValueError):
        return ()


def _catalog_class(label: str) -> ItemClass | None:
    try:
        from app.engine.records import load_catalog

        for item in load_catalog():
            if item.label == label:
                return ItemClass(str(item.item_class))
    except (OSError, KeyError, ValueError):
        return None
    return None


def _digest(text: str | bytes) -> int:
    raw = text.encode("utf-8") if isinstance(text, str) else text
    return int(hashlib.sha1(raw, usedforsecurity=False).hexdigest(), 16)


def nearest_label(crop: bytes, labels: tuple[str, ...]) -> str:
    """The catalog label whose SHA-1 is closest to the crop's. Same bytes, same answer."""
    if not labels:
        return FALLBACK_LABEL
    target = _digest(crop)
    return min(labels, key=lambda label: abs(_digest(label) - target))


def _decoys(label: str, labels: tuple[str, ...]) -> list[str]:
    """Two other catalog labels, picked the same way every time."""
    others = [name for name in sorted(labels) if name != label]
    if not others:
        return []
    start = _digest(label) % len(others)
    return [others[(start + offset) % len(others)] for offset in range(min(2, len(others)))]


class StubVisionProvider:
    """Deterministic vision. Used when no key is set and in every test."""

    name = STUB_NAME

    def __init__(self, queue: ExpectQueue | None = None) -> None:
        self._queue = queue
        self.last_call: CallUsage | None = None

    @property
    def queue(self) -> ExpectQueue:
        return self._queue if self._queue is not None else get_expect_queue()

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        started = time.perf_counter()
        labels = context.catalog_labels or _catalog_labels()
        expected = self.queue.pop()
        label = expected.label if expected is not None else nearest_label(crop, labels)
        known = label in labels
        confidence = CONFIDENT_P if known else UNSURE_P
        item_class = _catalog_class(label) or ItemClass.untracked

        spare = 1.0 - confidence
        candidates = [VisionCandidate(label=label, p=confidence)]
        for share, decoy in zip((0.6, 0.4), _decoys(label, labels), strict=False):
            candidates.append(VisionCandidate(label=decoy, p=round(spare * share, 4)))

        self.last_call = CallUsage(
            provider=STUB_NAME,
            model=STUB_NAME,
            tokens_in=0,
            tokens_out=0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_microusd=0,
            price_known=True,
        )
        return VisionResult.model_validate(
            {
                "label": label,
                "class": item_class,
                "confidence": confidence,
                "candidates": [c.model_dump() for c in candidates],
                "condition": "unknown",
                "visible_text": "",
                "provider": STUB_NAME,
                "model": STUB_NAME,
            }
        )


# Fixed ranges in whole cents, by class. Nothing here is a measurement, so the demo never
# shows one of these without the "est." tag the dashboard puts on a model_estimate source.
_RANGES: dict[ItemClass, dict[str, tuple[int, int, int]]] = {
    ItemClass.inventory: {
        "fmv": (50, 150, 300),
        "repair": (0, 0, 0),
        "replacement": (100, 200, 400),
        "scrap": (0, 0, 0),
    },
    ItemClass.fixed_asset: {
        "fmv": (2_000, 6_000, 12_000),
        "repair": (1_500, 3_500, 7_000),
        "replacement": (8_000, 15_000, 30_000),
        "scrap": (25, 100, 300),
    },
    ItemClass.untracked: {
        "fmv": (200, 800, 2_000),
        "repair": (500, 1_500, 4_000),
        "replacement": (1_000, 3_000, 8_000),
        "scrap": (10, 50, 200),
    },
}


class StubEstimatorProvider:
    """Fixed ranges by class. The caller decides what source to record them under."""

    name = STUB_NAME

    def __init__(self) -> None:
        self.last_call: CallUsage | None = None

    def estimate(
        self, label: str, vision: VisionResult, mass_g: float, crop: bytes | None = None,
        detail: str = "",
    ) -> ValueEstimate:
        started = time.perf_counter()
        table = _RANGES[vision.item_class]
        rationale = f"stub range for a {vision.item_class.value} item"
        self.last_call = CallUsage(
            provider=STUB_NAME,
            model=STUB_NAME,
            tokens_in=0,
            tokens_out=0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_microusd=0,
            price_known=True,
        )
        return ValueEstimate.model_validate(
            {
                "label": normalise_label(label),
                "fmv": _range(table["fmv"], rationale),
                "repair": _range(table["repair"], rationale),
                "replacement": _range(table["replacement"], rationale),
                "scrap": _range(table["scrap"], rationale),
                "material_mix": ({str(vision.material): 1.0} if vision.material else {}),
                "regulatory_flags": [],
                "provider": STUB_NAME,
                "model": STUB_NAME,
            }
        )


def _range(values: tuple[int, int, int], rationale: str) -> MoneyRange:
    low, mid, high = values
    return MoneyRange(low=low, mid=mid, high=high, rationale=rationale)
