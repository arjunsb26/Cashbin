"""Frame picking and crop tests. PLAN.md section 7."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.detect.crop import CropParams, Frame, crop_item, pick_frames
from app.detect.steps import Step

WIDTH = 640
HEIGHT = 480
RECT = (260, 180, 120, 90)  # x, y, w, h


def background(seed: int = 2) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((HEIGHT, WIDTH, 3), 70, dtype=np.uint8)
    noise = rng.integers(-6, 7, size=img.shape, dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def with_rect(
    base: np.ndarray,
    rect: tuple[int, int, int, int],
    colour: tuple[int, int, int],
) -> np.ndarray:
    img = base.copy()
    x, y, w, h = rect
    cv2.rectangle(img, (x, y), (x + w, y + h), colour, thickness=-1)
    return img


def jpeg(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    assert ok
    return bytes(buf.tobytes())


def a_step(t_open: float = 2000.0, t_settle: float = 2800.0) -> Step:
    return Step(
        kind="toss",
        t_open_ms=t_open,
        t_settle_ms=t_settle,
        mass_g=95.0,
        mass_err_g=0.4,
        baseline_before_g=0.0,
        baseline_after_g=95.0,
    )


def test_crop_finds_the_rectangle_that_appeared() -> None:
    base = background()
    before = jpeg(base)
    after = jpeg(with_rect(base, RECT, (40, 160, 220)))

    result = crop_item(before, after)

    assert result.crop_quality == "good"
    x, y, w, h = RECT
    params = CropParams()
    pad = max(params.pad_min_px, round(params.pad_frac * max(w, h)))
    tol = pad + 8
    assert abs(result.bbox.x - x) <= tol
    assert abs(result.bbox.y - y) <= tol
    assert abs((result.bbox.x + result.bbox.w) - (x + w)) <= tol
    assert abs((result.bbox.y + result.bbox.h) - (y + h)) <= tol
    assert result.changed_area_frac == pytest.approx((w * h) / (WIDTH * HEIGHT), rel=0.2)

    cut = cv2.imdecode(np.frombuffer(result.jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert cut.shape[0] == result.bbox.h
    assert cut.shape[1] == result.bbox.w


def test_identical_frames_give_low_quality_and_the_whole_frame() -> None:
    base = background()
    result = crop_item(jpeg(base), jpeg(base))

    assert result.crop_quality == "low"
    assert result.changed_area_frac < CropParams().min_area_frac
    assert (result.bbox.x, result.bbox.y, result.bbox.w, result.bbox.h) == (0, 0, WIDTH, HEIGHT)


def test_a_full_frame_change_gives_low_quality() -> None:
    base = background()
    flooded = np.full_like(base, 230)
    result = crop_item(jpeg(base), jpeg(flooded))

    assert result.crop_quality == "low"
    assert result.changed_area_frac > CropParams().max_area_frac
    assert (result.bbox.w, result.bbox.h) == (WIDTH, HEIGHT)


def test_a_speck_of_change_is_too_small_to_crop() -> None:
    base = background()
    speck = with_rect(base, (10, 10, 6, 6), (255, 255, 255))
    result = crop_item(jpeg(base), jpeg(speck))

    assert result.crop_quality == "low"


def test_pick_frames_chooses_before_after_and_peak() -> None:
    base = background()
    step = a_step()
    frames = [
        Frame(t_ms=1000.0, jpeg=jpeg(base)),
        Frame(t_ms=1600.0, jpeg=jpeg(base)),
        Frame(t_ms=2100.0, jpeg=jpeg(np.full_like(base, 255))),
        Frame(t_ms=2400.0, jpeg=jpeg(with_rect(base, RECT, (40, 160, 220)))),
        Frame(t_ms=2900.0, jpeg=jpeg(with_rect(base, RECT, (40, 160, 220)))),
        Frame(t_ms=3400.0, jpeg=jpeg(with_rect(base, RECT, (40, 160, 220)))),
    ]

    pick = pick_frames(frames, step)

    assert pick.complete
    assert pick.before is not None and pick.before.t_ms == 1600.0
    assert pick.after is not None and pick.after.t_ms == 2900.0
    assert pick.peak is not None and pick.peak.t_ms == 2100.0


def test_pick_frames_falls_back_when_the_buffer_is_short() -> None:
    base = background()
    step = a_step()
    frames = [
        Frame(t_ms=1900.0, jpeg=jpeg(base)),
        Frame(t_ms=2500.0, jpeg=jpeg(with_rect(base, RECT, (40, 160, 220)))),
    ]

    pick = pick_frames(frames, step)

    assert pick.before is not None and pick.before.t_ms == 1900.0
    assert pick.after is not None and pick.after.t_ms == 2500.0


def test_pick_frames_on_an_empty_buffer_returns_nothing() -> None:
    pick = pick_frames([], a_step())
    assert not pick.complete
    assert pick.before is None
    assert pick.after is None
    assert pick.peak is None


def test_unreadable_bytes_raise() -> None:
    with pytest.raises(ValueError, match="before frame"):
        crop_item(b"not an image", jpeg(background()))


def test_frames_of_different_sizes_still_crop() -> None:
    base = background()
    small = cv2.resize(base, (320, 240))
    after = with_rect(base, RECT, (40, 160, 220))

    result = crop_item(jpeg(small), jpeg(after))

    assert result.crop_quality == "good"
