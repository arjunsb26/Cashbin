"""The phone camera ring buffer.

PLAN.md section 7 asks for the last 4 s of frames so the crop can reach back before a
step opened. Frames arrive as JPEG bytes on `/ws/phone` and are stamped with the
backend arrival clock, the same clock the weight samples use.

Nothing here decodes an image. The ring holds bytes and hands out `detect.crop.Frame`
objects, which is exactly what `pick_frames` wants.
"""

from __future__ import annotations

from collections import deque

from app.detect.crop import Frame

DEFAULT_WINDOW_S = 4.0
DEFAULT_MAX_FRAMES = 256


class FrameRing:
    """The last `window_s` seconds of camera frames, oldest first.

    Eviction is by the newest stamp rather than by reading the clock, so a ring that
    stops being fed keeps what it has instead of quietly emptying itself. A hard frame
    cap is there as well, because a phone that sends faster than it promised should
    cost memory in proportion to the promise, not to the burst.
    """

    def __init__(
        self,
        window_s: float = DEFAULT_WINDOW_S,
        max_frames: int = DEFAULT_MAX_FRAMES,
    ) -> None:
        self.window_ms = window_s * 1000.0
        self.max_frames = max_frames
        self._frames: deque[Frame] = deque()
        self._newest_ms = 0.0
        self.received = 0

    def __len__(self) -> int:
        return len(self._frames)

    @property
    def newest_ms(self) -> float:
        """Arrival stamp of the most recent frame, or 0.0 when the ring is empty."""
        return self._newest_ms

    def push(self, jpeg: bytes, t_ms: float) -> Frame:
        """Add one frame and drop whatever has fallen out of the window."""
        frame = Frame(t_ms=t_ms, jpeg=jpeg)
        self._frames.append(frame)
        self.received += 1
        if t_ms > self._newest_ms:
            self._newest_ms = t_ms
        self._evict()
        return frame

    def snapshot(self) -> list[Frame]:
        """Every frame currently held, oldest first. A copy, so the caller can keep it."""
        return list(self._frames)

    def latest(self) -> Frame | None:
        return self._frames[-1] if self._frames else None

    def clear(self) -> None:
        self._frames.clear()
        self._newest_ms = 0.0

    def _evict(self) -> None:
        cutoff = self._newest_ms - self.window_ms
        while self._frames and self._frames[0].t_ms < cutoff:
            self._frames.popleft()
        while len(self._frames) > self.max_frames:
            self._frames.popleft()
