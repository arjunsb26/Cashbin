"""The pipeline end to end against the stub: QR, memory, the ask, fusion and failure."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import (
    Providers,
    build_providers,
    identify_event,
)
from app.identify.providers import CallUsage, IdentifyContext
from app.identify.stub import StubEstimatorProvider, StubVisionProvider, get_expect_queue
from app.learn.corrections import apply_correction
from app.models import (
    Asset,
    CatalogItem,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
    TaxMethod,
)
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, CHANNEL_UI
from app.schemas import CorrectionCreate, VisionResult
from tests.test_identify_support import (
    Listener,
    RecordingFinal,
    make_deps,
    make_event,
    make_jpeg,
    qr_jpeg,
    setup_db,
    write_crop,
)

CROP = make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200))
OTHER_CROP = make_jpeg(colour=(20, 20, 20), patch=(220, 220, 220))


class ScriptedVision:
    """A vision provider a test writes the answer for."""

    name = "stub"

    def __init__(self, result: VisionResult | None = None, delay: float = 0.0,
                 error: Exception | None = None) -> None:
        self.result = result
        self.delay = delay
        self.error = error
        self.last_call: CallUsage | None = None
        self.calls = 0

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def scripted(result: VisionResult | None = None, **kwargs: Any) -> Providers:
    return Providers(
        vision=ScriptedVision(result, **kwargs), estimator=StubEstimatorProvider(), name="stub"
    )


def vision(label: str, confidence: float, *candidates: tuple[str, float]) -> VisionResult:
    return VisionResult.model_validate(
        {
            "label": label,
            "class": "inventory",
            "confidence": confidence,
            "candidates": [{"label": name, "p": p} for name, p in candidates],
            "provider": "stub",
            "model": "stub",
        }
    )


def rows_for(event_id: int) -> list[Identification]:
    with session_scope() as session:
        return list(
            session.execute(
                select(Identification)
                .where(Identification.event_id == event_id)
                .order_by(Identification.id)
            ).scalars()
        )


def seed_catalog(label: str, mean_g: float, var: float, n: int) -> None:
    with session_scope() as session:
        session.add(
            CatalogItem(
                label=label,
                item_class=ItemClass.inventory,
                mass_prior_mean_g=mean_g,
                mass_prior_var=var,
                mass_prior_n=n,
            )
        )


# QR -------------------------------------------------------------------------


async def test_a_tagged_asset_is_identified_with_no_call(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        session.add(
            Asset(
                tag="bb-0002",
                description="Mechanical keyboard",
                cost_cents=12_000,
                in_service_date="2025-02-01",
                book_life_months=36,
                tax_method=TaxMethod.bonus_100,
            )
        )
        event = make_event(session, mass_g=780.0)
        event_id = event.id

    finals = RecordingFinal()
    deps = make_deps(settings, providers=scripted(), on_final=finals)
    outcome = await identify_event(event_id, CROP, [qr_jpeg("bb-0002")], 780.0, 3.0, deps)

    assert outcome.final is True
    assert outcome.label == "bb-0002"
    assert outcome.method is IdentifyMethod.qr
    assert outcome.item_class is ItemClass.fixed_asset
    assert finals.calls == [(event_id, "bb-0002", ItemClass.fixed_asset, IdentifyMethod.qr)]

    rows = rows_for(event_id)
    assert [r.method for r in rows] == [IdentifyMethod.qr]
    assert rows[0].confidence == 1.0
    assert rows[0].is_final is True
    assert (rows[0].provider, rows[0].model) == ("local", "qr-tag")
    assert rows[0].cost_microusd == 0
    assert deps.providers.vision.calls == 0  # type: ignore[attr-defined]

    with session_scope() as session:
        settled = session.get(type(event), event_id)
        assert settled is not None and settled.status is EventStatus.identified


# The confident path and the ask ---------------------------------------------


async def test_a_confident_stub_answer_is_final(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session).id
    get_expect_queue().push("bagel")

    listener = Listener(CHANNEL_BIN)
    deps = make_deps(settings)
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)

    assert outcome.final is True
    assert outcome.label == "bagel"
    assert outcome.method is IdentifyMethod.stub
    rows = rows_for(event_id)
    # The call's own row says which provider served it. The mass prior then writes a row of
    # its own on top, which is the fusion stage and is served locally.
    served = next(row for row in rows if row.provider == "stub")
    assert served.model == "stub"
    assert rows[-1].is_final is True
    assert rows[-1].label == "bagel"
    assert listener.types()[0] == "screen"


async def test_an_unsure_answer_opens_the_ask_on_all_three_surfaces(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session).id
    get_expect_queue().push("cracked phone")

    ui = Listener(CHANNEL_UI)
    phone = Listener(CHANNEL_PHONE)
    bin_screen = Listener(CHANNEL_BIN)
    finals = RecordingFinal()
    deps = make_deps(settings, on_final=finals)

    outcome = await identify_event(event_id, CROP, [], 180.0, 2.0, deps)

    assert outcome.final is False
    assert finals.calls == []
    assert str(outcome.candidates[0].label) == "cracked phone"
    assert "ask.opened" in ui.types()
    assert "ask" in [m.type for m in phone.messages()]  # type: ignore[attr-defined]
    screens = bin_screen.messages()
    assert [getattr(m, "s", "") for m in screens] == ["thinking", "ask"]
    with session_scope() as session:
        assert session.execute(select(Identification.event_id)).scalars().first() == event_id
    assert rows_for(event_id)[-1].is_final is False


async def test_the_ask_carries_at_most_four_candidates(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session).id
    many = vision(
        "one", 0.3, *[(name, 0.2) for name in ("two", "three", "four", "five", "six")]
    )
    deps = make_deps(settings, providers=scripted(many))
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)
    assert outcome.final is False
    assert 1 <= len(outcome.candidates) <= 4


# Memory ---------------------------------------------------------------------


async def test_the_second_toss_of_the_same_thing_is_surer_but_still_asks_the_model(
    settings: Settings,
) -> None:
    """PLAN.md 21a item 23. Memory used to answer here and skip the call. It now backs the
    call's answer instead, which is what turns an ask into a posted ticket."""
    setup_db(settings)
    name = write_crop(settings, "crop-1.jpg", CROP)
    with session_scope() as session:
        first = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("cracked phone")

    deps = make_deps(settings)
    assert (await identify_event(first, CROP, [], 180.0, 2.0, deps)).final is False

    answered = await apply_correction(
        CorrectionCreate(event_id=first, label="cracked phone"), deps
    )
    assert answered.status is EventStatus.confirmed
    assert len(deps.memory) == 1

    with session_scope() as session:
        second = make_event(session, mass_g=182.0, crop=name).id
    get_expect_queue().push("cracked phone")
    outcome = await identify_event(second, CROP, [], 182.0, 2.0, deps)

    assert outcome.final is True
    assert outcome.label == "cracked phone"
    # The model was asked, and it is the model's row that is final.
    assert outcome.method is IdentifyMethod.stub
    assert get_expect_queue().pending() == 0
    rows = rows_for(second)
    remembered = [row for row in rows if row.method is IdentifyMethod.memory]
    assert len(remembered) == 1
    assert remembered[0].is_final is False
    assert (remembered[0].provider, remembered[0].model) == ("local", "baseline-hsv-thumb")
    # The drawer gets the neighbours and how far away they were.
    assert "cracked phone" in json.loads(remembered[0].posterior_json or "{}")


async def test_a_remembered_example_that_agrees_turns_an_ask_into_an_answer(
    settings: Settings,
) -> None:
    setup_db(settings)
    name = write_crop(settings, "crop-2.jpg", CROP)
    with session_scope() as session:
        first = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("cracked phone")
    deps = make_deps(settings)
    assert (await identify_event(first, CROP, [], 180.0, 2.0, deps)).final is False
    await apply_correction(CorrectionCreate(event_id=first, label="cracked phone"), deps)

    # The same unsure answer the stub gave the first time, now with one example behind it.
    with session_scope() as session:
        second = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("cracked phone")
    outcome = await identify_event(second, CROP, [], 180.0, 2.0, deps)
    assert outcome.final is True, "an agreeing example is what stops the second ask"


async def test_a_different_object_does_not_match_the_exemplar(settings: Settings) -> None:
    setup_db(settings)
    name = write_crop(settings, "crop-1.jpg", CROP)
    with session_scope() as session:
        first = make_event(session, crop=name).id
    get_expect_queue().push("cracked phone")
    deps = make_deps(settings)
    await identify_event(first, CROP, [], 180.0, 2.0, deps)
    await apply_correction(CorrectionCreate(event_id=first, label="cracked phone"), deps)

    with session_scope() as session:
        second = make_event(session).id
    get_expect_queue().push("bagel")
    outcome = await identify_event(second, OTHER_CROP, [], 95.0, 2.0, deps)
    assert outcome.label == "bagel"
    assert outcome.method is IdentifyMethod.stub


# Mass prior fusion -----------------------------------------------------------


async def test_fusion_settles_a_split_answer_and_says_so(settings: Settings) -> None:
    setup_db(settings)
    seed_catalog("bagel", mean_g=95.0, var=100.0, n=6)
    seed_catalog("keyboard", mean_g=900.0, var=2500.0, n=6)
    with session_scope() as session:
        event_id = make_event(session, mass_g=96.0).id

    split = vision("bagel", 0.5, ("bagel", 0.5), ("keyboard", 0.5))
    deps = make_deps(settings, providers=scripted(split))
    outcome = await identify_event(event_id, CROP, [], 96.0, 2.0, deps)

    assert outcome.final is True
    assert outcome.label == "bagel"
    rows = rows_for(event_id)
    assert [r.used_mass_prior for r in rows] == [False, True]
    assert rows[-1].confidence is not None and rows[-1].confidence > 0.9
    assert rows[0].posterior_json is not None


async def test_without_a_usable_prior_nothing_is_fused(settings: Settings) -> None:
    setup_db(settings)
    seed_catalog("bagel", mean_g=95.0, var=100.0, n=1)
    with session_scope() as session:
        event_id = make_event(session, mass_g=96.0).id
    deps = make_deps(settings, providers=scripted(vision("bagel", 0.95, ("bagel", 0.95))))
    await identify_event(event_id, CROP, [], 96.0, 2.0, deps)
    assert [r.used_mass_prior for r in rows_for(event_id)] == [False]


# Failure --------------------------------------------------------------------


async def test_a_timeout_opens_the_ask_and_never_raises(settings: Settings) -> None:
    setup_db(settings)
    # Both goes time out. One that does not is a different case, below: the second call is
    # the whole point of the retry, so this one has to outlast it too.
    settings.llm_timeout_s = 0.05
    settings.vision_retry_timeout_s = 0.05
    with session_scope() as session:
        event_id = make_event(session).id
    deps = make_deps(settings, providers=scripted(vision("bagel", 0.99), delay=0.4))

    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)
    assert outcome.final is False
    # PLAN.md 21a item 36: a call that gave nothing offers nothing. The question is the
    # picture and Something else, not three catalog rows that weigh about the same.
    assert outcome.candidates == ()
    with session_scope() as session:
        from app.models import Event

        waiting = session.get(Event, event_id)
        assert waiting is not None and waiting.status is EventStatus.asking


async def test_a_provider_that_blows_up_opens_the_ask(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session).id
    deps = make_deps(settings, providers=scripted(error=RuntimeError("no network")))
    outcome = await identify_event(event_id, CROP, [], 95.0, 2.0, deps)
    assert outcome.final is False
    assert rows_for(event_id)[-1].label is None


async def test_an_unknown_event_is_an_error(settings: Settings) -> None:
    setup_db(settings)
    with pytest.raises(ValueError, match="does not exist"):
        await identify_event(9999, CROP, [], 95.0, 2.0, make_deps(settings))


# Provider choice -------------------------------------------------------------


def test_the_stub_is_the_default(settings: Settings) -> None:
    assert build_providers(settings).name == "stub"
    assert isinstance(build_providers(settings).vision, StubVisionProvider)


def test_a_provider_without_a_key_is_still_the_stub(settings: Settings) -> None:
    settings.llm_provider = "openai"
    assert build_providers(settings).name == "stub"


def test_a_provider_with_a_key_is_the_openai_adapter(settings: Settings) -> None:
    settings.llm_provider = "openai"
    settings.openai_api_key = "not-a-real-key"
    settings.llm_vision_model = "test-vision-model"
    providers = build_providers(settings)
    assert providers.name == "openai"
    assert type(providers.vision).__name__ == "OpenAIVisionProvider"


def test_an_unknown_provider_name_falls_back_to_the_stub(settings: Settings) -> None:
    settings.llm_provider = "something-else"
    settings.openai_api_key = "not-a-real-key"
    assert build_providers(settings).name == "stub"
