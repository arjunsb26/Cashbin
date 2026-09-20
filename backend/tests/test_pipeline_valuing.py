"""The value estimate is not allowed to hold up the answer.

PLAN.md 21a item 25. Lane K measured the estimator slower than the vision call on every
single ticket, and it only runs for labels the catalog does not price, which is every
electronic thing in the demo. That put an unpriced ticket at six seconds against three for
a bagel. So the label and the mass go out as soon as identification is final, and the
figure follows when the second call lands.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import Providers
from app.identify.providers import CallUsage
from app.models import Event, EventKind, EventStatus, IdentifyMethod, ItemClass, ItemRecord
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, get_bus
from app.pipeline import VALUING_BIG, VALUING_LINE, PipelineDeps, build_pipeline
from app.schemas import ScreenResult, ValueEstimate
from tests.test_identify_support import Listener, setup_db

SLOW_S = 0.25


def an_estimate(label: str) -> ValueEstimate:
    return ValueEstimate.model_validate(
        {
            "label": label,
            "fmv": {"low": 400, "mid": 600, "high": 800},
            "repair": {"low": 0, "mid": 0, "high": 0},
            "replacement": {"low": 1000, "mid": 1200, "high": 1400},
            "scrap": {"low": 10, "mid": 20, "high": 30},
            "material_mix": {"mixed_electronics": 1.0},
        }
    )


class SlowEstimator:
    """Costs what Lane K measured the real one costing, and counts its calls."""

    name = "stub"

    def __init__(self, delay_s: float = SLOW_S) -> None:
        self.delay_s = delay_s
        self.last_call: CallUsage | None = None
        self.calls = 0

    def estimate(
        self, label: str, vision: object, mass_g: float, crop: bytes | None = None,
        detail: str = "",
    ) -> ValueEstimate:
        self.calls += 1
        time.sleep(self.delay_s)
        return an_estimate(label)


def a_pipeline(settings: Settings, estimator: SlowEstimator) -> PipelineDeps:
    from app.db import get_session_factory

    pipe = build_pipeline(settings, get_session_factory(), get_bus())
    pipe.providers = Providers(
        vision=pipe.providers.vision, estimator=estimator, name="stub"
    )
    return pipe


def a_toss(mass_g: float = 62.0) -> int:
    with session_scope() as session:
        row = Event(kind=EventKind.toss, mass_g=mass_g, status=EventStatus.identified)
        session.add(row)
        session.flush()
        return int(row.id)


async def test_the_bin_is_answered_before_the_value_is_known(settings: Settings) -> None:
    setup_db(settings)

    event_id = a_toss()
    estimator = SlowEstimator()
    pipe = a_pipeline(settings, estimator)

    bin_screens = Listener(CHANNEL_BIN)
    phone_results = Listener(CHANNEL_PHONE)

    started = time.perf_counter()
    task = asyncio.create_task(
        pipe.finalise_event(event_id, "mystery gadget", ItemClass.untracked, IdentifyMethod.stub)
    )
    # Let the first pass run, and stop well before the estimator could have answered.
    await asyncio.sleep(SLOW_S / 4)
    first = [str(getattr(m, "big", "")) for m in phone_results.messages()]
    assert VALUING_BIG in first, "the phone was left waiting for the second model call"
    assert (time.perf_counter() - started) < SLOW_S

    screens = [
        m for m in bin_screens.messages() if isinstance(m, ScreenResult)
    ]
    assert screens, "the bin was left on the thinking screen"
    assert screens[0].big == VALUING_BIG
    assert screens[0].l2 == VALUING_LINE

    await task
    assert estimator.calls == 1
    later = [str(getattr(m, "big", "")) for m in phone_results.messages()]
    assert later and later[-1] != VALUING_BIG, "the figure never reached the phone"

    with session_scope() as session:
        record = session.get(ItemRecord, event_id)
        assert record is not None
        assert record.fmv_mid == 600
        row = session.get(Event, event_id)
        assert row is not None
        assert row.status is EventStatus.posted


async def test_a_priced_catalog_item_is_never_valued_twice(settings: Settings) -> None:
    setup_db(settings)

    event_id = a_toss(mass_g=95.0)
    estimator = SlowEstimator()
    pipe = a_pipeline(settings, estimator)

    phone_results = Listener(CHANNEL_PHONE)
    await pipe.finalise_event(event_id, "bagel", ItemClass.inventory, IdentifyMethod.stub)

    assert estimator.calls == 0, "the catalog prices a bagel, so nothing is estimated"
    bigs = [str(getattr(m, "big", "")) for m in phone_results.messages()]
    assert bigs and VALUING_BIG not in bigs, "a priced item is answered once, with its figure"


async def test_a_value_that_lands_after_a_correction_is_dropped(settings: Settings) -> None:
    """The figure belongs to the thing that was asked about, not to whatever it is now."""
    setup_db(settings)

    event_id = a_toss()
    estimator = SlowEstimator()
    pipe = a_pipeline(settings, estimator)

    task = asyncio.create_task(
        pipe.finalise_event(event_id, "mystery gadget", ItemClass.untracked, IdentifyMethod.stub)
    )
    await asyncio.sleep(SLOW_S / 4)
    # A person answers again while the estimate is still out.
    with session_scope() as session:
        record = session.get(ItemRecord, event_id)
        assert record is not None
        record.label = "something else"
    await task

    with session_scope() as session:
        record = session.get(ItemRecord, event_id)
        assert record is not None
        assert record.label == "something else"
        assert record.fmv_mid is None, "the old label's value must not land on the new one"


def test_the_waiting_copy_fits_every_surface() -> None:
    from app.schemas import LCD_BIG_MAX, LCD_LINE_MAX

    assert len(VALUING_BIG) <= LCD_BIG_MAX
    assert len(VALUING_LINE) <= LCD_LINE_MAX
    assert VALUING_LINE[0].isupper()
    assert pytest.approx(0) == len(VALUING_LINE.strip()) - len(VALUING_LINE)
