"""An untracked thing that is already on the register, and nobody put a tag on it.

PLAN.md 21a item 30. The camera says "wireless mouse" and the register says "Wireless
mouse, BB-0007, still in use". Those are probably the same object, and the difference
between them is a book loss and a tax line. So the bin asks, with the register row as the
first answer, and one tap writes the asset off properly.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import IdentifyDeps, identify_event
from app.models import (
    Asset,
    AssetStatus,
    Event,
    EventStatus,
    ItemClass,
    ItemRecord,
    TaxMethod,
)
from app.notify.bus import CHANNEL_PHONE, get_bus
from app.schemas import CorrectionCreate, CorrectionResponse, PhoneAsk, VisionResult
from tests.test_identify_pipeline import CROP, scripted
from tests.test_identify_support import (
    Listener,
    RecordingFinal,
    make_deps,
    make_event,
    setup_db,
)

TAG = "BB-0007"


def a_register_row(
    settings: Settings,
    description: str = "Wireless mouse",
    tag: str = TAG,
    status: AssetStatus = AssetStatus.active,
) -> None:
    setup_db(settings)
    today = date.today()
    with session_scope() as session:
        session.add(
            Asset(
                tag=tag,
                description=description,
                category="peripheral",
                cost_cents=4_900,
                in_service_date=today.replace(year=today.year - 1).isoformat(),
                book_life_months=36,
                salvage_cents=0,
                tax_method=TaxMethod.straight_line,
                status=status,
            )
        )


def a_sighting(label: str, visible_text: str = "") -> VisionResult:
    return VisionResult.model_validate(
        {
            "label": label,
            "class": "untracked",
            "confidence": 0.95,
            "description": f"a {label} on a desk",
            "visible_text": visible_text,
            "provider": "stub",
            "model": "stub",
        }
    )


async def an_untracked_toss(
    settings: Settings, label: str, visible_text: str = ""
) -> tuple[int, RecordingFinal, object]:
    """Run one toss the camera calls `label` and hand back what happened."""
    final = RecordingFinal()
    deps = make_deps(
        settings, providers=scripted(a_sighting(label, visible_text)), on_final=final
    )
    with session_scope() as session:
        event = make_event(session, mass_g=96.0)
        event_id = int(event.id)
    outcome = await identify_event(event_id, CROP, [], 96.0, 2.0, deps=deps)
    return event_id, final, outcome


async def test_a_register_row_is_the_first_answer(settings: Settings) -> None:
    a_register_row(settings)
    phone = Listener(CHANNEL_PHONE)
    event_id, final, _outcome = await an_untracked_toss(settings, "wireless mouse")

    assert not final.calls, "the bin wrote it off as somebody's mouse without asking"
    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    assert asks, "the phone was never asked"
    ask = asks[-1]
    assert ask.question == "Is this your registered wireless mouse (BB-0007)?"
    assert [str(c.label) for c in ask.candidates] == [
        "bb-0007",
        "a different wireless mouse",
    ]

    with session_scope() as session:
        event = session.get(Event, event_id)
        assert event is not None
        assert event.status is EventStatus.asking


async def test_nothing_on_the_register_looks_like_it_so_nothing_is_asked(
    settings: Settings,
) -> None:
    a_register_row(settings)
    _event_id, final, _outcome = await an_untracked_toss(settings, "banana peel")

    assert final.calls, "a thing the register has never heard of should just go through"
    assert final.calls[-1][1] == "banana peel"
    assert final.calls[-1][2] is ItemClass.untracked


async def test_a_disposed_row_is_not_offered(settings: Settings) -> None:
    a_register_row(settings, status=AssetStatus.disposed)
    _event_id, final, _outcome = await an_untracked_toss(settings, "wireless mouse")

    assert final.calls, "a row already off the register is not a candidate"


async def test_the_text_on_the_thing_finds_the_row(settings: Settings) -> None:
    """The label alone misses "dell usb keyboard". The brand printed on it does not."""
    a_register_row(settings, description="Dell USB keyboard", tag="BB-0011")
    phone = Listener(CHANNEL_PHONE)
    _event_id, final, _outcome = await an_untracked_toss(
        settings, "keyboard", visible_text="DELL"
    )

    assert not final.calls
    asks = [m for m in phone.messages() if isinstance(m, PhoneAsk)]
    assert asks and str(asks[-1].candidates[0].label) == "bb-0011"


# What the two answers do ------------------------------------------------------


async def a_pipeline_behind_the_ask(
    settings: Settings, label: str
) -> tuple[int, IdentifyDeps]:
    """The same ask, with the real engine attached to the answer."""
    from app.db import get_session_factory
    from app.identify.pipeline import Providers
    from app.pipeline import build_pipeline
    from tests.test_pipeline_valuing import SlowEstimator

    a_register_row(settings)
    pipe = build_pipeline(settings, get_session_factory(), get_bus())
    pipe.providers = Providers(
        vision=pipe.providers.vision, estimator=SlowEstimator(0.0), name="stub"
    )
    pipe.result_hold_s = 0.0
    deps = make_deps(settings, providers=scripted(a_sighting(label)))
    deps.on_final = pipe.finalise_event
    with session_scope() as session:
        event = make_event(session, mass_g=96.0)
        event_id = int(event.id)
    await identify_event(event_id, CROP, [], 96.0, 2.0, deps=deps)
    return event_id, deps


async def test_the_tag_answer_writes_the_asset_off(settings: Settings) -> None:
    event_id, deps = await a_pipeline_behind_the_ask(settings, "wireless mouse")

    await apply(deps, event_id, "bb-0007")

    with session_scope() as session:
        asset = session.scalars(select(Asset).where(Asset.tag == TAG)).first()
        assert asset is not None
        assert asset.status is AssetStatus.disposed
        assert asset.disposed_event_id == event_id
        record = session.get(ItemRecord, event_id)
        assert record is not None
        assert record.item_class is ItemClass.fixed_asset
        assert record.book_value_cents > 0
        assert record.asset_id == asset.id


async def test_the_other_answer_carries_on_as_an_untracked_thing(
    settings: Settings,
) -> None:
    event_id, deps = await a_pipeline_behind_the_ask(settings, "wireless mouse")

    answered = await apply(deps, event_id, "a different wireless mouse")

    assert answered.label == "wireless mouse", "the answer was a refusal, not a name"
    with session_scope() as session:
        asset = session.scalars(select(Asset).where(Asset.tag == TAG)).first()
        assert asset is not None
        assert asset.status is AssetStatus.active
        record = session.get(ItemRecord, event_id)
        assert record is not None
        assert record.item_class is ItemClass.untracked
        assert record.label == "wireless mouse"


async def apply(deps: IdentifyDeps, event_id: int, label: str) -> CorrectionResponse:
    from app.learn.corrections import apply_correction

    return await apply_correction(
        CorrectionCreate.model_validate(
            {"event_id": event_id, "label": label, "by": "phone"}
        ),
        deps=deps,
    )


@pytest.mark.parametrize(
    ("label", "visible_text", "description", "matched"),
    [
        ("wireless mouse", "", "Wireless mouse", True),
        ("mouse", "", "Wireless mouse", True),
        ("keyboard", "", "Dell keyboard", True),
        ("usb cable", "", "USB hub", False),
        ("pencil", "", "Wireless mouse", False),
        ("", "", "Wireless mouse", False),
        ("keyboard", "DELL", "Dell USB keyboard", True),
    ],
)
def test_what_counts_as_the_same_thing(
    label: str, visible_text: str, description: str, matched: bool
) -> None:
    from app.identify.pipeline import looks_like_row

    assert looks_like_row(label, visible_text, description) is matched


def test_the_question_fits_the_phone(settings: Settings) -> None:
    from app.identify.pipeline import register_question
    from app.schemas import PhoneAsk as Ask

    long_one = register_question("bb-0007", "A very long description of a thing " * 3)
    assert len(long_one) <= Ask.model_fields["question"].metadata[0].max_length
    assert long_one.endswith("?")
