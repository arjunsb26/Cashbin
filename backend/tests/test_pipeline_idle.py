"""What the bin says when nobody is throwing anything away.

PLAN.md 21a item 45. The user's words: "have the est value of whats inside live update".
A result stands for its hold and then the screen goes back to the running total of what is
in the bag: the money recorded, the weight, and how many things are in there. A bag change
empties the bag, so the total starts again from nothing.
"""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.db import session_scope
from app.detect.steps import Step
from app.identify.pipeline import Providers
from app.models import Event, EventKind, EventStatus, IdentifyMethod, ItemClass
from app.notify import lcd
from app.notify.bus import CHANNEL_BIN, get_bus
from app.pipeline import PipelineDeps, build_pipeline
from app.schemas import ScreenResult
from tests.test_identify_support import Listener, setup_db
from tests.test_pipeline_valuing import SlowEstimator


def a_pipeline(settings: Settings) -> PipelineDeps:
    from app.db import get_session_factory

    pipe = build_pipeline(settings, get_session_factory(), get_bus())
    pipe.providers = Providers(
        vision=pipe.providers.vision, estimator=SlowEstimator(0.0), name="stub"
    )
    # The hold is real on the bin and nothing to wait out in a test.
    pipe.result_hold_s = 0.0
    return pipe


def a_toss(mass_g: float) -> int:
    with session_scope() as session:
        row = Event(kind=EventKind.toss, mass_g=mass_g, status=EventStatus.identified)
        session.add(row)
        session.flush()
        return int(row.id)


def a_bag_change(mass_g: float = 480.0) -> int:
    with session_scope() as session:
        row = Event(kind=EventKind.bag_change, mass_g=mass_g, status=EventStatus.detected)
        session.add(row)
        session.flush()
        return int(row.id)


async def settle(pipe: PipelineDeps) -> None:
    """Let the hold task that the result scheduled run to its end."""
    for _ in range(4):
        await asyncio.sleep(0)
    task = pipe.idle_task
    if task is not None:
        await task


def idle_screens(listener: Listener) -> list[ScreenResult]:
    return [
        m
        for m in listener.messages()
        if isinstance(m, ScreenResult) and m.l1 == lcd.IDLE_HEADLINE
    ]


async def test_two_tosses_then_a_bag_change(settings: Settings) -> None:
    setup_db(settings)
    pipe = a_pipeline(settings)
    screens = Listener(CHANNEL_BIN)

    first = a_toss(62.0)
    await pipe.finalise_event(first, "mystery gadget", ItemClass.untracked, IdentifyMethod.stub)
    await settle(pipe)
    after_one = idle_screens(screens)
    assert after_one, "the bin never went back to the running total"
    assert after_one[-1].big == "$6.00"
    assert after_one[-1].l2 == "62 g, 1 item"

    second = a_toss(138.0)
    await pipe.finalise_event(second, "odd widget", ItemClass.untracked, IdentifyMethod.stub)
    await settle(pipe)
    after_two = idle_screens(screens)
    assert after_two[-1].big == "$12.00"
    assert after_two[-1].l2 == "200 g, 2 items"

    pipe.on_bag_change(a_bag_change())
    emptied = idle_screens(screens)
    assert emptied[-1].big == "$0.00"
    assert emptied[-1].l2 == lcd.IDLE_EMPTY


async def test_a_bag_change_off_the_scale_puts_the_empty_total_up(settings: Settings) -> None:
    """The hook is on the ingest seam, so a real bag change reaches the screen."""
    from app.ingest.events import create_event_from_step
    from app.ingest.state import IngestState

    setup_db(settings)
    pipe = a_pipeline(settings)
    ingest = IngestState(settings=settings, bus=get_bus())
    pipe.attach(ingest)

    first = a_toss(62.0)
    await pipe.finalise_event(first, "mystery gadget", ItemClass.untracked, IdentifyMethod.stub)
    await settle(pipe)

    screens = Listener(CHANNEL_BIN)
    await create_event_from_step(
        Step(
            kind="bag_change",
            t_open_ms=0.0,
            t_settle_ms=900.0,
            mass_g=-480.0,
            mass_err_g=1.0,
            baseline_before_g=480.0,
            baseline_after_g=0.0,
        ),
        ingest,
    )

    emptied = idle_screens(screens)
    assert emptied, "the bag went out and the bin kept showing the old total"
    assert emptied[-1].big == "$0.00"
    assert emptied[-1].l2 == lcd.IDLE_EMPTY


async def test_the_hold_is_cancelled_by_the_next_toss(settings: Settings) -> None:
    """A second toss lands inside the hold, so the idle screen never covers its result."""
    setup_db(settings)
    pipe = a_pipeline(settings)
    pipe.result_hold_s = 30.0

    first = a_toss(62.0)
    await pipe.finalise_event(first, "mystery gadget", ItemClass.untracked, IdentifyMethod.stub)
    held = pipe.idle_task
    assert held is not None

    second = a_toss(138.0)
    await pipe.finalise_event(second, "odd widget", ItemClass.untracked, IdentifyMethod.stub)
    await asyncio.sleep(0)
    assert held.cancelled(), "the first hold was left running against the second result"

    pipe.cancel_hold()
