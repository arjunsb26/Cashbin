"""The sense gate where a person meets it: on the bin, the phone and the ticket.

PLAN.md 21a item 50. The unit cases live in `test_sense_check.py`. These three go through
the real finalisation path, because a verdict that never reaches a surface is not a gate.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent import sense_check
from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import Providers, write_identification
from app.models import (
    Event,
    EventKind,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
    JournalEntry,
)
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, get_bus
from app.pipeline import PipelineDeps, build_pipeline
from app.schemas import PhoneAsk, PhoneResult, ScreenResult, VisionResult
from tests.test_identify_support import Listener, setup_db
from tests.test_pipeline_valuing import SlowEstimator


def a_pipeline(settings: Settings) -> PipelineDeps:
    from app.db import get_session_factory

    pipe = build_pipeline(settings, get_session_factory(), get_bus())
    pipe.providers = Providers(
        vision=pipe.providers.vision, estimator=SlowEstimator(0.0), name="stub"
    )
    return pipe


def a_toss(label: str, description: str, mass_g: float = 24.0) -> int:
    with session_scope() as session:
        row = Event(kind=EventKind.toss, mass_g=mass_g, status=EventStatus.identified)
        session.add(row)
        session.flush()
        write_identification(
            session,
            event_id=int(row.id),
            method=IdentifyMethod.stub,
            label=label,
            item_class=ItemClass.untracked,
            confidence=0.9,
            posterior={label: 0.9},
            is_final=True,
            description=description,
        )
        return int(row.id)


def a_vision(label: str, description: str) -> VisionResult:
    return VisionResult.model_validate(
        {
            "label": label,
            "class": "untracked",
            "confidence": 0.9,
            "description": description,
            "provider": "stub",
            "model": "test",
        }
    )


@pytest.fixture(autouse=True)
def _clean_cache() -> None:
    sense_check.reset_cache()


async def test_a_veto_opens_an_ask_instead_of_a_confident_ticket(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_db(settings)
    event_id = a_toss("laptop charger", "small black usb stick", mass_g=18.0)
    pipe = a_pipeline(settings)
    pipe.vision.remember(event_id, a_vision("laptop charger", "small black usb stick"))

    def vetoed(*args: object, **kwargs: object) -> sense_check.SenseCheck:
        return sense_check.SenseCheck(
            verdict="veto",
            reason="the picture is a usb stick and the label says laptop charger",
        )

    monkeypatch.setattr(sense_check, "check", vetoed)

    phone = Listener(CHANNEL_PHONE)
    await pipe.finalise_event(
        event_id, "laptop charger", ItemClass.untracked, IdentifyMethod.stub
    )

    with session_scope() as session:
        event = session.get(Event, event_id)
        assert event is not None
        assert event.status is EventStatus.asking
        assert (
            session.scalars(
                select(JournalEntry.id).where(JournalEntry.event_id == event_id)
            ).first()
            is None
        )
        row = session.scalars(
            select(Identification)
            .where(Identification.event_id == event_id)
            .order_by(Identification.id.desc())
        ).first()
        assert row is not None
        stored = json.loads(row.posterior_json or "{}")
        assert stored["sense_check"]["verdict"] == "veto"

    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    assert asks, "the phone was never asked"
    assert asks[-1].looks_like == "small black usb stick"
    assert not [m for m in phone.messages() if isinstance(m, PhoneResult)]


async def test_a_rewrite_is_the_line_the_bin_draws(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_db(settings)
    event_id = a_toss("aa battery", "a small alkaline battery")
    pipe = a_pipeline(settings)
    pipe.vision.remember(event_id, a_vision("aa battery", "a small alkaline battery"))

    def rewritten(*args: object, **kwargs: object) -> sense_check.SenseCheck:
        return sense_check.SenseCheck(
            verdict="rewrite",
            headline="Aa Battery",
            line2="Recycle, not trash",
            reason="a battery is never repaired",
            best_option="recycle",
        )

    monkeypatch.setattr(sense_check, "check", rewritten)

    screens = Listener(CHANNEL_BIN)
    await pipe.finalise_event(event_id, "aa battery", ItemClass.untracked, IdentifyMethod.stub)

    drawn = [m for m in screens.messages() if isinstance(m, ScreenResult)]
    assert drawn, "the bin drew no result"
    assert drawn[-1].l2 == "Recycle, not trash"


async def test_the_verdict_is_filed_on_the_identification_row(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_db(settings)
    event_id = a_toss("pencil", "a yellow wooden pencil")
    pipe = a_pipeline(settings)
    pipe.vision.remember(event_id, a_vision("pencil", "a yellow wooden pencil"))

    def agreed(*args: object, **kwargs: object) -> sense_check.SenseCheck:
        return sense_check.SenseCheck(verdict="sensible", reason="that reads fine")

    monkeypatch.setattr(sense_check, "check", agreed)
    await pipe.finalise_event(event_id, "pencil", ItemClass.untracked, IdentifyMethod.stub)

    with session_scope() as session:
        row = session.scalars(
            select(Identification)
            .where(Identification.event_id == event_id)
            .order_by(Identification.id.desc())
        ).first()
        assert row is not None
        stored = json.loads(row.posterior_json or "{}")
        assert stored["sense_check"]["verdict"] == "sensible"
        assert stored["sense_check"]["reason"] == "that reads fine"
