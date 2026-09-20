"""Pick the frames around a step and cut the new item out of them.

PLAN.md section 7. Pure functions over decoded frames and JPEG bytes. Nothing here
writes to disk. The ingest layer saves what comes back under `/media/{event_id}/`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict

from app.detect.steps import Step

CropQuality = Literal["good", "low"]


class Frame(BaseModel):
    """One camera frame. `t_ms` is the backend arrival clock, the same clock as weight."""

    model_config = ConfigDict(frozen=True)

    t_ms: float
    jpeg: bytes


class FramePick(BaseModel):
    """The three frames worth keeping for one step."""

    before: Frame | None = None
    after: Frame | None = None
    peak: Frame | None = None

    @property
    def complete(self) -> bool:
        return self.before is not None and self.after is not None


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class CropParams(BaseModel):
    # How far before the step opens the `before` frame must sit. PLAN.md section 7
    # says 300 ms, which assumes the item appears in frame at the moment it lands.
    # It does not: it is in shot for the whole flight, and the simulator gives it a
    # 300 ms flight. A lead equal to the flight time picks a frame that already has
    # the item in it and the diff comes back empty, so this has to be longer. The
    # phone ring buffer covers 4 s, so 600 ms costs nothing.
    before_lead_ms: float = 600.0
    blur_ksize: int = 5
    threshold: int = 25
    close_ksize: int = 15
    min_area_frac: float = 0.002
    max_area_frac: float = 0.5
    pad_frac: float = 0.08
    pad_min_px: int = 8
    jpeg_quality: int = 85


class CropResult(BaseModel):
    """The cut-out item, plus enough to explain why it looks the way it does."""

    jpeg: bytes
    bbox: BBox
    changed_area_frac: float
    crop_quality: CropQuality


def pick_frames(
    frames: Sequence[Frame],
    step: Step,
    params: CropParams | None = None,
) -> FramePick:
    """Choose the before, after and peak frames for a step.

    `before` is the last frame older than the open minus `before_lead_ms`, so the item
    is certainly not in it yet. `after` is the first frame at or past the settle.
    `peak` is the frame ending the largest frame-to-frame change between the before
    frame and the settle, which is usually the item in the air or sitting on top.

    When the ring buffer does not reach back far enough, `before` falls back to the
    oldest frame before the open. When nothing arrived after the settle, `after` falls
    back to the newest frame after the open. Either can still come back as None, and
    the caller then has an event with no image.
    """
    p = params or CropParams()
    ordered = sorted(frames, key=lambda f: f.t_ms)
    if not ordered:
        return FramePick()

    cutoff = step.t_open_ms - p.before_lead_ms
    earlier = [f for f in ordered if f.t_ms <= cutoff]
    before = earlier[-1] if earlier else next((f for f in ordered if f.t_ms < step.t_open_ms), None)

    later = [f for f in ordered if f.t_ms >= step.t_settle_ms]
    after: Frame | None
    if later:
        after = later[0]
    else:
        newer = [f for f in ordered if f.t_ms > step.t_open_ms]
        after = newer[-1] if newer else None

    peak_from = before.t_ms if before is not None else cutoff
    during = [f for f in ordered if peak_from <= f.t_ms <= step.t_settle_ms]
    peak = _peak_frame(during) or after
    return FramePick(before=before, after=after, peak=peak)


def whole_frame(image: bytes, params: CropParams | None = None) -> CropResult:
    """The picture as it stands, with no diff.

    The diff exists to find the thing that just landed in a bin full of other things. When
    somebody holds an item up and presses Add, the picture is the item: diffing it against
    a frame from two seconds earlier found the table, because the table is what changed
    least. The quality is `low`, which is honest: nothing was isolated.
    """
    p = params or CropParams()
    return _whole_frame(_decode(image, "added item"), 0.0, p)


def crop_item(before: bytes, after: bytes, params: CropParams | None = None) -> CropResult:
    """Cut the thing that appeared between two frames out of the second one.

    Grayscale, blur, absolute difference, threshold, morphological close, largest
    contour, padded bounding box. When the changed area falls outside
    `min_area_frac..max_area_frac` the crop is the whole `after` frame and the quality
    is `low`, which the UI shows and the identifier treats as weaker evidence.
    """
    p = params or CropParams()
    img_before = _decode(before, "before")
    img_after = _decode(after, "after")
    if img_before.shape != img_after.shape:
        img_before = cv2.resize(img_before, (img_after.shape[1], img_after.shape[0]))

    height, width = img_after.shape[:2]
    frame_area = float(height * width)
    mask = _change_mask(img_before, img_after, p)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return _whole_frame(img_after, 0.0, p)

    largest = max(contours, key=cv2.contourArea)
    frac = float(cv2.contourArea(largest)) / frame_area
    if frac < p.min_area_frac or frac > p.max_area_frac:
        return _whole_frame(img_after, frac, p)

    x, y, w, h = (int(v) for v in cv2.boundingRect(largest))
    pad = max(p.pad_min_px, round(p.pad_frac * max(w, h)))
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + w + pad)
    y1 = min(height, y + h + pad)
    bbox = BBox(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
    return CropResult(
        jpeg=_encode(img_after[y0:y1, x0:x1], p),
        bbox=bbox,
        changed_area_frac=frac,
        crop_quality="good",
    )


def _peak_frame(frames: Sequence[Frame]) -> Frame | None:
    if len(frames) < 2:
        return None
    grays = [_gray_small(_decode(f.jpeg, "peak")) for f in frames]
    best_i = 1
    best_score = -1.0
    for i in range(1, len(grays)):
        score = float(np.mean(cv2.absdiff(grays[i - 1], grays[i])))
        if score > best_score:
            best_score = score
            best_i = i
    return frames[best_i]


def _gray_small(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (160, 120))


def _change_mask(before: np.ndarray, after: np.ndarray, p: CropParams) -> np.ndarray:
    k = p.blur_ksize | 1
    g_before = cv2.GaussianBlur(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY), (k, k), 0)
    g_after = cv2.GaussianBlur(cv2.cvtColor(after, cv2.COLOR_BGR2GRAY), (k, k), 0)
    diff = cv2.absdiff(g_before, g_after)
    _, mask = cv2.threshold(diff, p.threshold, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (p.close_ksize | 1, p.close_ksize | 1))
    closed: np.ndarray = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return closed


def _whole_frame(img_after: np.ndarray, frac: float, p: CropParams) -> CropResult:
    height, width = img_after.shape[:2]
    return CropResult(
        jpeg=_encode(img_after, p),
        bbox=BBox(x=0, y=0, w=width, h=height),
        changed_area_frac=frac,
        crop_quality="low",
    )


def _decode(data: bytes, what: str) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"the {what} frame is not a readable image")
    return img


def _encode(img: np.ndarray, p: CropParams) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), p.jpeg_quality])
    if not ok:
        raise ValueError("could not encode the crop as JPEG")
    return bytes(buf.tobytes())


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """The width and height of a JPEG, or None when the bytes are not a picture."""
    if not data:
        return None
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    height, width = img.shape[:2]
    return width, height


def downscale_jpeg(data: bytes, max_px: int, quality: int = 80) -> bytes:
    """Re-encode a JPEG so its longest side is at most `max_px`.

    A model that classifies an object does not need a two megapixel photograph, and the
    upload is a real part of the wait: the picture travels as base64 inside the request.
    The full size crop stays on disk for the evidence drawer, so this shrinks a copy and
    never the file anyone looks at.

    Bytes that are already small enough come back as they are, and bytes that are not a
    picture come back untouched, because refusing to send anything would be worse than
    sending what we have.
    """
    # Empty bytes are not a picture either, and the decoder raises on them rather than
    # returning None, which is how a phantom toss with no camera crashed the vision step.
    if max_px <= 0 or not data:
        return data
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return data
    height, width = img.shape[:2]
    longest = max(height, width)
    if longest <= max_px:
        return data
    scale = max_px / float(longest)
    small = cv2.resize(
        img,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    ok, buffer = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return data
    return bytes(buffer.tobytes())
