"""A toss with no picture asks a person, and never hands empty bytes to a decoder.

Found on the real board: with the camera not yet plugged in, the floating scale pin made
phantom tosses, and each one sent an empty crop to the vision call, which crashed inside
the image decoder twice per toss instead of opening an ask.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from app.detect import crop as crop_module
from app.identify import pipeline


def test_empty_bytes_never_reach_the_decoder() -> None:
    assert crop_module.downscale_jpeg(b"", 384) == b""
    assert crop_module.jpeg_size(b"") is None


@pytest.mark.asyncio
async def test_a_toss_with_no_picture_makes_no_vision_call(monkeypatch: pytest.MonkeyPatch) -> None:
    async def must_not_run(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the vision call ran on an empty crop")

    monkeypatch.setattr(pipeline, "_call_vision", must_not_run)
    context = cast(Any, type("Ctx", (), {"event_id": 80})())
    answer, task = await pipeline._two_goes(cast(Any, object()), b"", context)
    assert answer is None
    assert task is None
