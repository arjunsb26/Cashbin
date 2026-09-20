"""The model may only answer with a label the books already know.

PLAN.md 21a item 27. Lane K's bench: at effort `none`, eleven of sixty eight answers on
real photographs were wrong, and every one of them came back at confidence 0.97 or better,
so `confident_p` cannot separate them. Two were labels the model invented, which the
catalog cannot price and the ledger cannot post.

So the label is an enum of the catalog plus "unknown". Structured outputs refuses anything
else at the host, and the adapter refuses it again here, because a wall that only exists in
somebody else's process is not a wall.
"""

from __future__ import annotations

import json

from app.config import Settings
from app.identify.openai_request import (
    UNKNOWN_CHOICE,
    build_vision_request,
    label_enum,
    strict_schema,
)
from app.identify.providers import IdentifyContext
from app.schemas import VisionResult
from tests.test_identify_openai import FakeClient
from tests.test_identify_support import make_jpeg

CATALOG = ("bagel", "usb cable", "hdmi cable")


def _context(labels: tuple[str, ...] = CATALOG) -> IdentifyContext:
    return IdentifyContext(
        event_id=3, mass_g=140.0, mass_err_g=2.0, timeout_s=8.0, catalog_labels=labels
    )


def _settings() -> Settings:
    return Settings(
        _env_file=None, llm_vision_model="gpt-5.6-luna", openai_api_key="x"
    )


def _reply(label: str) -> str:
    return json.dumps({"label": label, "class": "untracked", "confidence": 0.98})


# The schema -------------------------------------------------------------------


def test_the_label_is_an_enum_of_the_catalog_plus_unknown() -> None:
    schema = label_enum(strict_schema(VisionResult, drop=("provider", "model")), CATALOG)
    assert schema["properties"]["label"]["enum"] == [*CATALOG, UNKNOWN_CHOICE]


def test_a_candidate_is_held_to_the_same_list() -> None:
    schema = label_enum(strict_schema(VisionResult, drop=("provider", "model")), CATALOG)
    inner = schema["$defs"]["VisionCandidate"]["properties"]["label"]
    assert inner["enum"] == [*CATALOG, UNKNOWN_CHOICE]


def test_the_request_carries_the_enum_and_the_task_says_so() -> None:
    request = build_vision_request(make_jpeg(), _context(), "test-vision-model")
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["label"]["enum"] == [*CATALOG, UNKNOWN_CHOICE]
    task = request["messages"][1]["content"][0]["text"]
    assert UNKNOWN_CHOICE in task


def test_a_repeated_catalog_label_is_listed_once() -> None:
    schema = label_enum(
        strict_schema(VisionResult, drop=("provider", "model")), ("bagel", "bagel")
    )
    assert schema["properties"]["label"]["enum"] == ["bagel", UNKNOWN_CHOICE]


# The adapter ------------------------------------------------------------------


def test_a_label_the_books_do_not_know_is_refused_and_asked_again() -> None:
    from app.identify.openai_provider import FALLBACK_CONFIDENCE, OpenAIVisionProvider

    client = FakeClient([_reply("usb wall charger"), _reply("usb wall charger")])
    provider = OpenAIVisionProvider(_settings(), client=client)
    answer = provider.identify(make_jpeg(), _context())

    assert len(client.calls) == 2, "an answer outside the catalog is asked again, once"
    # And having been asked twice, it is not an answer at all, so a person is asked.
    assert answer.confidence == FALLBACK_CONFIDENCE
    assert str(answer.label) == "unknown object"


def test_the_retry_is_taken_when_the_second_answer_is_a_real_one() -> None:
    from app.identify.openai_provider import OpenAIVisionProvider

    client = FakeClient([_reply("usb wall charger"), _reply("usb cable")])
    provider = OpenAIVisionProvider(_settings(), client=client)
    answer = provider.identify(make_jpeg(), _context())

    assert len(client.calls) == 2
    assert str(answer.label) == "usb cable"
    assert answer.confidence == 0.98


def test_a_catalog_label_is_taken_first_time() -> None:
    from app.identify.openai_provider import OpenAIVisionProvider

    client = FakeClient([_reply("bagel")])
    provider = OpenAIVisionProvider(_settings(), client=client)
    answer = provider.identify(make_jpeg(), _context())

    assert len(client.calls) == 1
    assert str(answer.label) == "bagel"


def test_unknown_is_an_answer_the_model_is_allowed_to_give() -> None:
    from app.identify.openai_provider import OpenAIVisionProvider

    client = FakeClient([_reply(UNKNOWN_CHOICE)])
    provider = OpenAIVisionProvider(_settings(), client=client)
    answer = provider.identify(make_jpeg(), _context())

    assert len(client.calls) == 1, "saying so is not a failure, so nothing is retried"
    assert str(answer.label) == UNKNOWN_CHOICE


# Through identification --------------------------------------------------------


async def test_unknown_opens_the_ask_rather_than_becoming_a_label(
    settings: Settings,
) -> None:
    from app.db import session_scope
    from app.identify.pipeline import Providers, identify_event
    from app.identify.stub import StubEstimatorProvider
    from app.models import EventStatus
    from tests.test_identify_pipeline import ScriptedVision
    from tests.test_identify_support import make_deps, make_event, setup_db

    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=140.0).id

    said_unknown = VisionResult.model_validate(
        {"label": UNKNOWN_CHOICE, "class": "untracked", "confidence": 0.99}
    )
    providers = Providers(
        vision=ScriptedVision(said_unknown),
        estimator=StubEstimatorProvider(),
        name="stub",
    )
    outcome = await identify_event(
        event_id, make_jpeg(), [], 140.0, 2.0, make_deps(settings, providers=providers)
    )

    assert outcome.final is False, "an answer of unknown is a question, not a label"
    with session_scope() as session:
        from app.models import Event

        row = session.get(Event, event_id)
        assert row is not None
        assert row.status is EventStatus.asking
