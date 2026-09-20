"""A camera answer that is slow is not a camera answer that is missing.

The live case this exists for: a legible HP 32 GB flash drive, the vision call over five
seconds, the SDK quietly trying three times inside that budget, and the phone showing a
question with nothing in it but Something else. The user's words: "Do these options make
sense to you? What did i say about nonsense".

Nothing here talks to a model. A scripted provider is slow once, slow forever, or slow
enough that the answer lands after the question has already gone out.
"""

from __future__ import annotations

import asyncio
import time

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import (
    CAMERA_ANSWERED,
    NO_CAMERA_ANSWER,
    Providers,
    identify_event,
)
from app.identify.providers import CallUsage, IdentifyContext
from app.identify.stub import StubEstimatorProvider
from app.models import Event, EventStatus
from app.notify.bus import CHANNEL_PHONE, CHANNEL_UI
from app.schemas import PhoneAsk, UiAskOpened, UiAskResolved, VisionResult
from tests.test_identify_pipeline import CROP, vision
from tests.test_identify_support import Listener, RecordingFinal, make_deps, make_event, setup_db


class SlowThenAnswers:
    """Sleeps past the budget on the calls the test says, then answers at once."""

    name = "stub"

    def __init__(self, result: VisionResult, slow_calls: int, delay: float) -> None:
        self.result = result
        self.slow_calls = slow_calls
        self.delay = delay
        self.last_call: CallUsage | None = None
        self.calls = 0
        self.efforts: list[str] = []

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        self.calls += 1
        self.efforts.append(context.effort)
        if self.calls <= self.slow_calls:
            time.sleep(self.delay)
        return self.result


def providers(inner: SlowThenAnswers) -> Providers:
    return Providers(vision=inner, estimator=StubEstimatorProvider(), name="stub")


def an_event(settings: Settings) -> int:
    setup_db(settings)
    with session_scope() as session:
        return int(make_event(session).id)


async def test_one_slow_call_is_retried_rather_than_asked_about(settings: Settings) -> None:
    event_id = an_event(settings)
    settings.llm_timeout_s = 0.05
    settings.vision_retry_timeout_s = 2.0
    slow = SlowThenAnswers(vision("bagel", 0.99), slow_calls=1, delay=0.2)
    deps = make_deps(settings, providers=providers(slow))

    phone = Listener(CHANNEL_PHONE)
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)

    assert outcome.final is True
    assert outcome.label == "bagel"
    assert slow.calls == 2
    # The second go thinks a little, because at no effort the model would not name it.
    assert slow.efforts[1] == settings.vision_retry_effort
    assert not [m for m in phone.messages() if isinstance(m, PhoneAsk)]


async def test_both_goes_failing_asks_and_says_why(settings: Settings) -> None:
    event_id = an_event(settings)
    settings.llm_timeout_s = 0.05
    settings.vision_retry_timeout_s = 0.05
    slow = SlowThenAnswers(vision("bagel", 0.99), slow_calls=5, delay=0.4)
    deps = make_deps(settings, providers=providers(slow))

    phone = Listener(CHANNEL_PHONE)
    dashboard = Listener(CHANNEL_UI)
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)

    assert outcome.final is False
    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    opened = [m for m in dashboard.messages() if isinstance(m, UiAskOpened)]
    assert asks and opened
    assert asks[-1].question == NO_CAMERA_ANSWER
    assert opened[-1].question == NO_CAMERA_ANSWER


async def test_an_answer_that_lands_after_the_question_closes_it(settings: Settings) -> None:
    event_id = an_event(settings)
    settings.llm_timeout_s = 0.05
    settings.vision_retry_timeout_s = 0.05
    slow = SlowThenAnswers(vision("bagel", 0.99), slow_calls=2, delay=0.3)
    final = RecordingFinal()
    deps = make_deps(settings, providers=providers(slow), on_final=final)

    dashboard = Listener(CHANNEL_UI)
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)
    assert outcome.final is False

    for _ in range(60):
        await asyncio.sleep(0.05)
        with session_scope() as session:
            row = session.get(Event, event_id)
            if row is not None and row.status is not EventStatus.asking:
                break

    with session_scope() as session:
        row = session.get(Event, event_id)
        assert row is not None
        assert row.status is not EventStatus.asking

    resolved = [m for m in dashboard.messages() if isinstance(m, UiAskResolved)]
    assert resolved, "the dashboard was never told the question closed"
    assert resolved[-1].by == CAMERA_ANSWERED
    assert resolved[-1].label == "bagel"


async def test_a_person_who_already_answered_beats_the_late_camera(
    settings: Settings,
) -> None:
    event_id = an_event(settings)
    settings.llm_timeout_s = 0.05
    settings.vision_retry_timeout_s = 0.05
    slow = SlowThenAnswers(vision("bagel", 0.99), slow_calls=2, delay=0.3)
    deps = make_deps(settings, providers=providers(slow))

    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)
    assert outcome.final is False

    with session_scope() as session:
        row = session.get(Event, event_id)
        assert row is not None
        row.status = EventStatus.confirmed
        session.commit()

    dashboard = Listener(CHANNEL_UI)
    await asyncio.sleep(0.6)
    assert not [m for m in dashboard.messages() if isinstance(m, UiAskResolved)]
