"""Rounds and the numbers drawn from them. Every figure is read back out of the database."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import identify_event
from app.identify.stub import get_expect_queue
from app.learn import metrics, rounds
from app.learn.corrections import apply_correction
from app.models import (
    Event,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
    OptionKind,
    OptionScore,
    Round,
)
from app.notify.bus import CHANNEL_UI
from app.schemas import CorrectionCreate
from tests.test_identify_support import (
    Listener,
    make_deps,
    make_event,
    make_jpeg,
    setup_db,
    write_crop,
)

CROP = make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200))


def record(settings: Settings, *, asked: bool, confident: bool, cost: int | None = None) -> Round:
    with session_scope() as session:
        event = make_event(session)
        return rounds.record_event(
            session,
            settings,
            event=event,
            asked=asked,
            confident=confident,
            latency_ms=100,
            cost_microusd=cost,
        )


def test_the_first_event_opens_a_round(settings: Settings) -> None:
    setup_db(settings)
    rnd = record(settings, asked=False, confident=True)
    assert rnd.id == 1
    assert rnd.n_events == 1
    assert rnd.n_correct_first_try == 1
    assert rnd.ended_at is None


def test_counters_add_up(settings: Settings) -> None:
    setup_db(settings)
    record(settings, asked=False, confident=True, cost=120)
    record(settings, asked=True, confident=False, cost=340)
    rnd = record(settings, asked=False, confident=True, cost=None)
    assert (rnd.n_events, rnd.n_correct_first_try, rnd.n_asked) == (3, 2, 1)
    assert rnd.cloud_cost_microusd == 460
    assert rnd.mean_latency_ms == pytest.approx(100.0)

    read = metrics.round_read(rnd)
    assert read.first_try_accuracy == pytest.approx(2 / 3)
    assert read.ask_rate == pytest.approx(1 / 3)
    assert read.cost_per_event_microusd == pytest.approx(460 / 3)


def test_a_round_rolls_over_at_the_configured_size(settings: Settings) -> None:
    setup_db(settings)
    settings.round_size = 2
    record(settings, asked=False, confident=True)
    record(settings, asked=False, confident=True)
    third = record(settings, asked=False, confident=True)
    assert third.id == 2
    assert third.n_events == 1
    with session_scope() as session:
        first = session.get(Round, 1)
        assert first is not None and first.ended_at is not None


def test_starting_a_round_by_hand_closes_the_open_one(settings: Settings) -> None:
    setup_db(settings)
    record(settings, asked=False, confident=True)
    with session_scope() as session:
        fresh = rounds.start_round(session)
        assert fresh.id == 2
        closed = session.get(Round, 1)
        assert closed is not None and closed.ended_at is not None
        reopened = rounds.open_round(session)
        assert reopened is not None and reopened.id == 2


def test_an_empty_round_reports_no_rates_rather_than_zero(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        fresh = rounds.start_round(session)
        read = metrics.round_read(fresh, session)
    assert read.first_try_accuracy is None
    assert read.ask_rate is None
    assert read.local_share is None
    assert read.cost_per_event_microusd is None


async def test_the_local_share_counts_qr_only(settings: Settings) -> None:
    """PLAN.md 21a item 23. Memory no longer answers on its own, so a remembered example
    does not make an event free: the model was still asked. A QR tag is the only
    identification that costs nothing, and this number now says so."""
    setup_db(settings)
    name = write_crop(settings, "crop-1.jpg", CROP)
    deps = make_deps(settings)
    with session_scope() as session:
        first = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("cracked phone")
    await identify_event(first, CROP, [], 180.0, 2.0, deps)
    await apply_correction(CorrectionCreate(event_id=first, label="cracked phone"), deps)

    with session_scope() as session:
        second = make_event(session, mass_g=181.0, crop=name).id
    await identify_event(second, CROP, [], 181.0, 2.0, deps)

    with session_scope() as session:
        rnd = rounds.open_round(session)
        assert rnd is not None
        read = metrics.round_read(rnd, session)
        assert read.n_events == 2
        assert read.local_share == pytest.approx(0.0)
        assert read.ask_rate == pytest.approx(0.5)


def test_the_summary_reads_the_engines_option_rows(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event = make_event(session)
        session.add_all(
            [
                OptionScore(
                    event_id=event.id,
                    option=OptionKind.trash,
                    allowed=True,
                    net_after_tax_cents=-50,
                    kg_landfill=0.18,
                    rank=2,
                ),
                OptionScore(
                    event_id=event.id,
                    option=OptionKind.donate,
                    allowed=True,
                    net_after_tax_cents=120,
                    kg_landfill=0.0,
                    rank=1,
                ),
            ]
        )
    with session_scope() as session:
        found = metrics.summary(session)
    assert found.saved_if_followed_cents == 170
    assert found.kg_diverted == pytest.approx(0.18)
    assert found.events == 1


def test_the_summary_tolerates_an_empty_database(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        found = metrics.summary(session)
    assert found.saved_if_followed_cents == 0
    assert found.kg_diverted == 0.0
    assert found.events == 0
    assert found.first_try_accuracy is None


async def test_what_the_system_learned_reads_in_plain_words(settings: Settings) -> None:
    setup_db(settings)
    deps = make_deps(settings)
    name = write_crop(settings, "crop-1.jpg", CROP)

    with session_scope() as session:
        first = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("bagel")
    await identify_event(first, CROP, [], 180.0, 2.0, deps)
    await apply_correction(CorrectionCreate(event_id=first, label="cracked phone"), deps)

    with session_scope() as session:
        second = make_event(session, mass_g=182.0, crop=name, status=EventStatus.asking).id
    await apply_correction(CorrectionCreate(event_id=second, label="cracked phone"), deps)

    with session_scope() as session:
        sentences = metrics.what_learned(session)
    assert sentences == [
        "cracked phone: now recognised from 2 examples",
        "bagel vs cracked phone: now recognised from 2 examples",
    ]


async def test_metrics_are_pushed_to_the_dashboard_after_every_event(
    settings: Settings,
) -> None:
    setup_db(settings)
    listener = Listener(CHANNEL_UI)
    with session_scope() as session:
        event_id = make_event(session).id
    get_expect_queue().push("bagel")
    await identify_event(event_id, CROP, [], 95.0, 2.0, make_deps(settings))

    updates = [m for m in listener.messages() if getattr(m, "type", "") == "metrics.updated"]
    assert len(updates) == 1
    assert updates[0].summary.events == 1  # type: ignore[attr-defined]
    assert updates[0].round is not None  # type: ignore[attr-defined]


def test_the_rounds_list_is_oldest_first(settings: Settings) -> None:
    setup_db(settings)
    settings.round_size = 1
    record(settings, asked=False, confident=True)
    record(settings, asked=True, confident=False)
    with session_scope() as session:
        listed = metrics.list_rounds(session)
    assert [r.id for r in listed.rounds] == [1, 2]


def test_an_event_keeps_the_round_it_was_first_recorded_on(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event = make_event(session)
        rounds.record_event(session, settings, event=event, asked=True, confident=False)
        rounds.start_round(session)
        again = rounds.record_event(session, settings, event=event, asked=False, confident=True)
        assert again.id == 1
        assert event.round_id == 1


def test_a_final_human_row_does_not_count_as_local(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event = make_event(session)
        rnd = rounds.record_event(session, settings, event=event, asked=True, confident=False)
        session.add(
            Identification(
                event_id=event.id,
                method=IdentifyMethod.human,
                label="bagel",
                item_class=ItemClass.inventory,
                is_final=True,
            )
        )
        session.flush()
        assert metrics.local_share(session, rnd.id) == 0.0


def test_a_void_event_is_left_out_of_the_header(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        make_event(session, status=EventStatus.void)
        make_event(session, status=EventStatus.posted)
    with session_scope() as session:
        assert metrics.summary(session).events == 1
        assert session.execute(select(Event.id)).scalars().all() == [1, 2]
