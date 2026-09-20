"""The three knobs that decide how long a toss waits for its answer.

The user asked for one to two seconds from the item landing to the answer. Today the settle
costs most of a second and the model costs two to four more. These tests pin the parts of
that the backend controls: how the call is scheduled, how big the picture is, and whether
the call starts when the step opens rather than when it settles.
"""

from __future__ import annotations

import asyncio
import json
import time

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.detect.crop import downscale_jpeg, jpeg_size
from app.identify import early
from app.identify.openai_request import build_vision_request
from app.identify.pipeline import Providers
from app.identify.providers import IdentifyContext
from app.schemas import VisionResult
from tests.test_identify_openai import FakeClient
from tests.test_identify_support import make_deps, make_jpeg


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def _context() -> IdentifyContext:
    return IdentifyContext(
        event_id=1, mass_g=95.0, mass_err_g=2.0, timeout_s=8.0, catalog_labels=("bagel",)
    )


# The request ----------------------------------------------------------------


def test_the_request_asks_for_the_fast_queue_and_no_thinking() -> None:
    request = build_vision_request(
        make_jpeg(), _context(), "test-vision-model", "none", service_tier="fast"
    )
    assert request["reasoning_effort"] == "none"
    assert request["service_tier"] == "fast"


def test_the_default_tier_is_left_off_the_request() -> None:
    """"default" means an ordinary request, so the parameter is not sent at all."""
    request = build_vision_request(
        make_jpeg(), _context(), "test-vision-model", "low", service_tier="default"
    )
    assert "service_tier" not in request


def test_the_instruction_text_still_comes_before_the_per_toss_data() -> None:
    """Prompt caching bills the shared prefix, so nothing per toss may sit in front of it."""
    request = build_vision_request(make_jpeg(), _context(), "test-vision-model")
    system, user = request["messages"]
    task, data, image = user["content"]
    assert system["role"] == "system"
    assert task["type"] == "text"
    assert image["type"] == "image_url"
    keys = list(json.loads(data["text"]))
    assert keys == sorted(keys)
    assert keys.index("catalog_labels") < keys.index("mass_g")


# The picture ----------------------------------------------------------------


def _jpeg(width: int, height: int) -> bytes:
    img = np.random.default_rng(7).integers(0, 255, (height, width, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    assert ok
    return bytes(buf)


def test_a_big_crop_is_shrunk_to_the_longest_side() -> None:
    big = _jpeg(1600, 1200)
    assert jpeg_size(big) == (1600, 1200)
    small = downscale_jpeg(big, 512, 80)
    assert jpeg_size(small) == (512, 384)
    assert len(small) < len(big)


def test_a_small_crop_is_left_exactly_as_it_is() -> None:
    small = _jpeg(320, 240)
    assert downscale_jpeg(small, 512, 80) is small


def test_bytes_that_are_not_a_picture_come_back_unchanged() -> None:
    assert downscale_jpeg(b"not a jpeg", 512, 80) == b"not a jpeg"


def test_the_adapter_sends_the_shrunken_picture() -> None:
    from app.identify.openai_provider import OpenAIVisionProvider

    client = FakeClient(
        [json.dumps({"label": "bagel", "class": "inventory", "confidence": 0.9})]
    )
    provider = OpenAIVisionProvider(
        _settings(llm_vision_model="m", vision_image_max_px=64), client=client
    )
    provider.identify(_jpeg(1600, 1200), _context())
    url = client.calls[0]["messages"][1]["content"][2]["image_url"]["url"]
    import base64

    sent = base64.b64decode(url.split(",", 1)[1])
    assert jpeg_size(sent) == (64, 48)


# The early call -------------------------------------------------------------


async def test_the_early_slot_hands_the_result_to_whoever_asks_for_it() -> None:
    early.clear()
    result = VisionResult.model_validate(
        {"label": "bagel", "class": "inventory", "confidence": 0.9}
    )

    async def work() -> tuple[VisionResult | None, bytes | None]:
        return result, b"crop"

    early.start(opened_ms=100.0, work=work())
    assert early.take(1) is None, "an unclaimed slot belongs to no event yet"
    assert early.claim(100.0, 1) is True
    pending = early.take(1)
    assert pending is not None
    assert early.take(1) is None
    got, crop = await pending.result(timeout_s=2.0)
    assert got is result
    assert crop == b"crop"


async def test_a_slot_started_for_another_step_is_never_handed_over() -> None:
    """An answer about the wrong object is worse than no answer at all."""

    early.clear()

    async def work() -> tuple[VisionResult | None, bytes | None]:
        await asyncio.sleep(10.0)
        raise AssertionError("the call should have been cancelled")

    early.start(opened_ms=100.0, work=work())
    assert early.claim(250.0, 9) is False
    assert early.take(9) is None
    assert early.peek() is None


async def test_a_step_that_was_not_a_toss_cancels_the_early_call() -> None:
    early.clear()
    started = asyncio.Event()

    async def work() -> tuple[VisionResult | None, bytes | None]:
        started.set()
        await asyncio.sleep(10.0)
        raise AssertionError("the call should have been cancelled")

    early.start(opened_ms=0.0, work=work())
    await started.wait()
    early.cancel("the step was a bag change")
    await asyncio.sleep(0)
    assert early.take(1) is None


async def test_the_early_call_is_waited_for_rather_than_repeated() -> None:
    """The whole point: the model is already working while the scale is still settling."""

    early.clear()
    result = VisionResult.model_validate(
        {"label": "bagel", "class": "inventory", "confidence": 0.9}
    )

    async def work() -> tuple[VisionResult | None, bytes | None]:
        await asyncio.sleep(0.2)
        return result, None

    early.start(opened_ms=0.0, work=work())
    assert early.claim(0.0, 3) is True
    await asyncio.sleep(0.2)
    pending = early.take(3)
    assert pending is not None
    started = time.perf_counter()
    got, _ = await pending.result(timeout_s=2.0)
    assert got is result
    assert (time.perf_counter() - started) < 0.1


# The early call, end to end through identification --------------------------


async def test_identification_uses_the_call_that_was_already_running(
    settings: Settings,
) -> None:
    """The model was asked while the scale was settling, so nobody asks it again."""
    from app.db import session_scope
    from app.identify.pipeline import identify_event
    from app.identify.providers import EstimatorProvider
    from app.identify.stub import StubEstimatorProvider
    from tests.test_identify_pipeline import ScriptedVision, vision
    from tests.test_identify_support import make_event, setup_db

    early.clear()
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=95.0).id

    answer = vision("bagel", 0.95)
    spy = ScriptedVision(answer)
    estimator: EstimatorProvider = StubEstimatorProvider()
    providers = Providers(vision=spy, estimator=estimator, name="stub")

    async def work() -> tuple[VisionResult | None, bytes | None]:
        return answer, b"early crop"

    early.start(opened_ms=42.0, work=work())
    assert early.claim(42.0, event_id) is True

    deps = make_deps(settings, providers=providers)
    outcome = await identify_event(event_id, make_jpeg(), [], 95.0, 2.0, deps)

    assert outcome.final is True
    assert outcome.label == "bagel"
    assert spy.calls == 0, "the settle-time call was skipped"


async def test_an_early_call_that_gave_nothing_falls_back_to_a_fresh_one(
    settings: Settings,
) -> None:
    from app.db import session_scope
    from app.identify.pipeline import identify_event
    from app.identify.providers import EstimatorProvider
    from app.identify.stub import StubEstimatorProvider
    from tests.test_identify_pipeline import ScriptedVision, vision
    from tests.test_identify_support import make_event, setup_db

    early.clear()
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=95.0).id

    spy = ScriptedVision(vision("bagel", 0.95))
    estimator: EstimatorProvider = StubEstimatorProvider()
    providers = Providers(vision=spy, estimator=estimator, name="stub")

    async def work() -> tuple[VisionResult | None, bytes | None]:
        return None, None

    early.start(opened_ms=7.0, work=work())
    assert early.claim(7.0, event_id) is True

    deps = make_deps(settings, providers=providers)
    outcome = await identify_event(event_id, make_jpeg(), [], 95.0, 2.0, deps)

    assert outcome.final is True
    assert spy.calls == 1


def test_the_settings_route_carries_the_three_speed_knobs(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["llm_service_tier"] == "fast"
    assert body["llm_vision_effort"] == "none"
    assert body["llm_text_effort"] == "low"
    changed = client.patch(
        "/api/settings", json={"llm_service_tier": "default", "llm_vision_effort": "low"}
    )
    assert changed.status_code == 200
    assert changed.json()["llm_service_tier"] == "default"
    assert changed.json()["llm_vision_effort"] == "low"


def test_a_service_tier_the_host_would_refuse_is_refused_here(client: TestClient) -> None:
    assert client.patch("/api/settings", json={"llm_service_tier": "turbo"}).status_code == 422
    assert client.patch("/api/settings", json={"llm_vision_effort": "lots"}).status_code == 422
