"""The deterministic providers, the expect queue, and how the stub chooses a label."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.identify.providers import EstimatorProvider, IdentifyContext, VisionProvider
from app.identify.stub import (
    CONFIDENT_P,
    UNSURE_P,
    ExpectQueue,
    StubEstimatorProvider,
    StubVisionProvider,
    nearest_label,
)
from app.models import ItemClass
from tests.test_identify_support import make_jpeg

CATALOG = ("bagel", "cookie", "pizza slice", "usb cable")


def context(labels: tuple[str, ...] = CATALOG) -> IdentifyContext:
    return IdentifyContext(
        event_id=1, mass_g=95.0, mass_err_g=2.0, timeout_s=8.0, catalog_labels=labels
    )


def test_the_stubs_satisfy_the_protocols() -> None:
    assert isinstance(StubVisionProvider(), VisionProvider)
    assert isinstance(StubEstimatorProvider(), EstimatorProvider)


def test_the_queue_answers_first_and_only_once() -> None:
    queue = ExpectQueue()
    queue.push("  Pizza Slice ")
    provider = StubVisionProvider(queue)
    assert provider.identify(make_jpeg(), context()).label == "pizza slice"
    assert queue.pending() == 0
    second = provider.identify(make_jpeg(), context())
    assert second.label in CATALOG


def test_a_queued_label_that_is_not_in_the_catalog_opens_the_ask() -> None:
    queue = ExpectQueue()
    queue.push("cracked phone")
    result = StubVisionProvider(queue).identify(make_jpeg(), context())
    assert result.label == "cracked phone"
    assert result.confidence == UNSURE_P
    assert result.item_class is ItemClass.untracked


def test_a_catalog_label_comes_back_confident_with_two_decoys() -> None:
    queue = ExpectQueue()
    queue.push("bagel")
    result = StubVisionProvider(queue).identify(make_jpeg(), context())
    assert result.confidence == CONFIDENT_P
    assert result.candidates[0].label == "bagel"
    assert len(result.candidates) == 3
    assert sum(c.p for c in result.candidates) == pytest.approx(1.0, abs=0.01)


def test_with_an_empty_queue_the_same_crop_always_gives_the_same_label() -> None:
    crop = make_jpeg(patch=(200, 30, 30))
    first = StubVisionProvider(ExpectQueue()).identify(crop, context())
    second = StubVisionProvider(ExpectQueue()).identify(crop, context())
    assert first.label == second.label
    assert nearest_label(crop, CATALOG) == first.label


def test_every_answer_names_its_provider_and_model() -> None:
    provider = StubVisionProvider(ExpectQueue())
    result = provider.identify(make_jpeg(), context())
    assert result.provider == "stub"
    assert result.model == "stub"
    assert provider.last_call is not None
    assert provider.last_call.cost_microusd == 0


def test_an_empty_context_falls_back_to_the_seed_catalog() -> None:
    from app.engine.records import load_catalog

    result = StubVisionProvider(ExpectQueue()).identify(make_jpeg(), context(labels=()))
    assert str(result.label) in {item.label for item in load_catalog()}


def test_with_no_catalog_at_all_the_answer_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_file(*_args: object, **_kwargs: object) -> object:
        raise OSError("no catalog file")

    monkeypatch.setattr("app.engine.records.load_catalog", no_file)
    result = StubVisionProvider(ExpectQueue()).identify(make_jpeg(), context(labels=()))
    assert result.label == "unknown object"
    assert result.confidence == UNSURE_P
    assert result.candidates[0].label == "unknown object"


def test_the_simulator_can_queue_what_is_coming(dev_client: object) -> None:
    from fastapi.testclient import TestClient

    from app.identify.stub import get_expect_queue

    assert isinstance(dev_client, TestClient)
    response = dev_client.post("/api/sim/expect", json={"label": "Pizza Slice", "mass_g": 107.0})
    assert response.status_code == 200
    assert response.json() == {"label": "pizza slice", "mass_g": 107.0}
    assert get_expect_queue().pending() == 1

    queued = dev_client.post("/api/sim/expect", json={"label": "bagel"})
    assert queued.json() == {"label": "bagel", "mass_g": None}
    assert get_expect_queue().pending() == 2


def test_the_simulator_route_refuses_a_hostile_label(dev_client: object) -> None:
    from fastapi.testclient import TestClient

    assert isinstance(dev_client, TestClient)
    assert dev_client.post("/api/sim/expect", json={"label": "a" * 60}).status_code == 422


def test_the_estimator_gives_ordered_ranges_by_class(settings: Settings) -> None:
    queue = ExpectQueue()
    queue.push("cracked phone")
    vision = StubVisionProvider(queue).identify(make_jpeg(), context())
    estimate = StubEstimatorProvider().estimate("cracked phone", vision, 180.0)
    assert estimate.label == "cracked phone"
    assert estimate.fmv.low <= estimate.fmv.mid <= estimate.fmv.high
    assert estimate.repair.mid > 0
    assert estimate.provider == "stub"


def test_the_estimator_answers_for_every_class() -> None:
    queue = ExpectQueue()
    for item_class in ItemClass:
        queue.push("bagel" if item_class is ItemClass.inventory else "cracked phone")
        vision = StubVisionProvider(queue).identify(make_jpeg(), context())
        estimate = StubEstimatorProvider().estimate(str(vision.label), vision, 100.0)
        assert estimate.scrap.low <= estimate.scrap.high
