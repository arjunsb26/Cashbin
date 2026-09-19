"""Shared pieces for the ingest tests: a clock the test drives, and frames to crop.

Detection runs on the backend arrival clock, so a test that streamed a staircase as
fast as a socket allows would stamp every sample with the same millisecond and no step
would ever settle. Rather than spending real seconds, the tests hand the ingest state a
clock that walks the timeline the signal was built on.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import cv2
import numpy as np

from app.detect.steps import Sample

FRAME_W = 320
FRAME_H = 240


class ScriptedClock:
    """Returns the next stamp on a scripted timeline, one per call.

    The bin session calls it exactly once per weight message, so feeding it the times
    of the samples it is about to receive makes the arrival clock and the signal clock
    the same clock.
    """

    def __init__(self, times: Sequence[float], step_ms: float = 1000.0 / 15.0) -> None:
        self._times: Iterator[float] = iter(times)
        self.step_ms = step_ms
        self.last = 0.0

    def __call__(self) -> float:
        self.last = next(self._times, self.last + self.step_ms)
        return self.last


def weight_frames(samples: Sequence[Sample]) -> list[dict[str, object]]:
    """The samples as the bin sends them on the wire."""
    return [{"type": "weight", "t": int(s.t_ms), "g": round(s.g, 2)} for s in samples]


def jpeg(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("could not encode a test frame")
    return bytes(buffer.tobytes())


def background_frame(seed: int = 3) -> np.ndarray:
    """A mottled grey bin, the same every time, so a diff has real texture to ignore."""
    rng = np.random.default_rng(seed)
    base = np.full((FRAME_H, FRAME_W, 3), 90, dtype=np.uint8)
    noise = rng.integers(-10, 10, size=base.shape, dtype=np.int16)
    mottled: np.ndarray = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return mottled


def frame_with_item(background: np.ndarray) -> np.ndarray:
    """The same bin with something orange in it, about 6 percent of the frame."""
    image = background.copy()
    cv2.rectangle(image, (120, 90), (200, 150), (40, 120, 230), thickness=-1)
    return image
