"""The estimator: what it looks at, what effort it runs at, and how clean the figures come out.

PLAN.md 21a items 29 and 47. The bug this file exists for: the bin was shown a 150 dollar
mouse and said 12 dollars, because the estimate call saw the word "mouse" and a mass and
nothing else. Everything here runs against a fake client, so no key and no network.
"""

from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.identify.estimate_cache import reset_cache
from app.identify.openai_provider import OpenAIEstimatorProvider
from app.schemas import ValueEstimate, VisionResult
from tests.test_identify_openai import GOOD_ESTIMATE, FakeClient, conf
from tests.test_identify_support import make_jpeg, setup_db

MOUSE = VisionResult.model_validate(
    {
        "label": "mouse",
        "class": "untracked",
        "confidence": 0.93,
        "condition": "working",
        "description": "black wireless mouse with a thumb wheel",
        "visible_text": "MX Master 3",
    }
)
# Figures a model actually gives: averages of listings, to the cent.
MESSY_ESTIMATE = json.dumps(
    {
        "label": "mouse",
        "fmv": {"low": 900, "mid": 1173, "high": 1500, "rationale": "two used listings"},
        # A narrow range: the mid rounds past its own high, so the high has to follow.
        "repair": {"low": 9000, "mid": 9987, "high": 9990, "rationale": "shop rate"},
        "replacement": {"low": 9000, "mid": 12345, "high": 14000, "rationale": "retail"},
        "scrap": {"low": 20, "mid": 137, "high": 400, "rationale": "materials"},
        "material_mix": {"electronic_peripherals": 1.0},
        "regulatory_flags": ["electronics"],
    }
)


@pytest.fixture(autouse=True)
def _fresh_cache(settings: Settings) -> None:
    """Every case starts with an empty cache, so one price never answers for the next."""
    setup_db(settings)
    reset_cache()


def priced(client: FakeClient, **overrides: object) -> ValueEstimate:
    provider = OpenAIEstimatorProvider(conf(**overrides), client)
    return provider.estimate("mouse", MOUSE, 141.0, crop=make_jpeg(), detail="still works")


# What the estimator looks at -------------------------------------------------


def test_the_crop_goes_with_the_estimate_call() -> None:
    client = FakeClient([MESSY_ESTIMATE])
    priced(client)
    parts = client.calls[0]["messages"][1]["content"]
    assert [part["type"] for part in parts] == ["text", "text", "image_url"]
    assert parts[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_what_was_read_described_asked_and_seen_all_travel_as_data() -> None:
    client = FakeClient([MESSY_ESTIMATE])
    priced(client)
    sent = json.loads(client.calls[0]["messages"][1]["content"][1]["text"])
    assert sent["visible_text"] == "MX Master 3"
    assert sent["description"] == "black wireless mouse with a thumb wheel"
    assert sent["detail"] == "still works"
    assert sent["condition"] == "working"


def test_an_estimate_with_no_picture_still_works() -> None:
    """The ask path prices from a label and an answer, with no crop to hand."""
    client = FakeClient([MESSY_ESTIMATE])
    OpenAIEstimatorProvider(conf(), client).estimate("mouse", MOUSE, 141.0)
    parts = client.calls[0]["messages"][1]["content"]
    assert [part["type"] for part in parts] == ["text", "text"]


def test_the_estimate_call_runs_at_low_effort_on_the_fast_queue() -> None:
    """PLAN.md 21a items 26 and 29. Off the critical path, so it may think a little."""
    client = FakeClient([MESSY_ESTIMATE])
    priced(client, llm_estimate_effort="low", llm_service_tier="fast")
    assert client.calls[0]["reasoning_effort"] == "low"
    assert client.calls[0]["service_tier"] == "fast"


def test_a_setting_that_names_another_effort_is_obeyed() -> None:
    client = FakeClient([MESSY_ESTIMATE])
    priced(client, llm_estimate_effort="medium")
    assert client.calls[0]["reasoning_effort"] == "medium"


# How clean the figures come out ----------------------------------------------


def test_every_mid_is_cleaned_and_the_spread_is_left_alone() -> None:
    estimate = priced(FakeClient([MESSY_ESTIMATE]))
    assert (estimate.fmv.low, estimate.fmv.mid, estimate.fmv.high) == (900, 1150, 1500)
    assert estimate.replacement.mid == 12500
    assert estimate.scrap.mid == 150
    assert estimate.fmv.rationale == "two used listings"


def test_a_narrow_range_stays_in_order_after_cleaning() -> None:
    estimate = priced(FakeClient([MESSY_ESTIMATE]))
    assert estimate.repair.mid == 10000
    assert estimate.repair.low <= estimate.repair.mid <= estimate.repair.high
    assert estimate.repair.high == 10000


def test_a_clean_figure_is_left_where_it_is() -> None:
    estimate = OpenAIEstimatorProvider(conf(), FakeClient([GOOD_ESTIMATE])).estimate(
        "cracked phone", MOUSE, 180.0
    )
    assert (estimate.fmv.mid, estimate.repair.mid) == (2000, 8000)
    assert (estimate.replacement.mid, estimate.scrap.mid) == (40000, 50)


def test_the_row_says_which_model_served_it() -> None:
    estimate = priced(FakeClient([MESSY_ESTIMATE]))
    assert (estimate.provider, estimate.model) == ("openai", "test-text-model")
    assert str(estimate.label).startswith("mouse")


def test_the_cleaned_figure_is_what_gets_cached() -> None:
    """What the bin drew is what the dashboard shows an hour later, to the cent."""
    client = FakeClient([MESSY_ESTIMATE])
    first = priced(client)
    second = priced(client)
    assert len(client.calls) == 1
    assert second.fmv.mid == first.fmv.mid == 1150
