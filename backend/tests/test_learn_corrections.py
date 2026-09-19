"""What one answer from a person changes: the ticket, the memory, the prior and the round."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.identify.pipeline import identify_event
from app.identify.stub import get_expect_queue
from app.learn.corrections import CorrectionRefusedError, apply_correction
from app.learn.rounds import open_round
from app.models import (
    CatalogItem,
    Correction,
    Event,
    EventStatus,
    Exemplar,
    Identification,
    IdentifyMethod,
    ItemClass,
)
from app.notify.bus import CHANNEL_PHONE, CHANNEL_UI
from app.schemas import CorrectionCreate
from tests.test_identify_support import (
    Listener,
    RecordingFinal,
    make_deps,
    make_event,
    make_jpeg,
    setup_db,
    write_crop,
)

CROP = make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200))


async def ask_about(settings: Settings, deps: object, label: str = "cracked phone") -> int:
    """Run one event through to an ask, and give back its id."""
    name = write_crop(settings, "crop-ask.jpg", CROP)
    with session_scope() as session:
        event_id = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push(label)
    outcome = await identify_event(event_id, CROP, [], 180.0, 2.0, deps)  # type: ignore[arg-type]
    assert outcome.final is False
    return event_id


async def test_an_answer_settles_the_ticket_and_teaches_the_system(settings: Settings) -> None:
    setup_db(settings)
    finals = RecordingFinal()
    deps = make_deps(settings, on_final=finals)
    event_id = await ask_about(settings, deps)

    ui = Listener(CHANNEL_UI)
    phone = Listener(CHANNEL_PHONE)
    response = await apply_correction(
        CorrectionCreate(event_id=event_id, label="cracked phone"), deps
    )

    assert response.event_id == event_id
    assert response.label == "cracked phone"
    assert response.status is EventStatus.confirmed
    assert response.correction_id > 0

    with session_scope() as session:
        final = session.execute(
            select(Identification).where(
                Identification.event_id == event_id, Identification.is_final.is_(True)
            )
        ).scalars().all()
        assert len(final) == 1
        assert final[0].method is IdentifyMethod.human
        assert final[0].confidence == 1.0
        assert final[0].provider == "human"

        corrections = session.execute(select(Correction)).scalars().all()
        assert [c.field for c in corrections] == ["label"]
        assert corrections[0].new_value == "cracked phone"

        exemplars = session.execute(select(Exemplar)).scalars().all()
        assert [e.label for e in exemplars] == ["cracked phone"]
        assert exemplars[0].mass_g == 180.0

        catalog = session.execute(
            select(CatalogItem).where(CatalogItem.label == "cracked phone")
        ).scalars().one()
        assert catalog.item_class is ItemClass.untracked
        assert catalog.mass_prior_n == 1
        assert catalog.mass_prior_mean_g == 180.0

    assert "ask.resolved" in ui.types()
    assert "idle" in phone.types()
    assert finals.calls[-1] == (
        event_id,
        "cracked phone",
        ItemClass.untracked,
        IdentifyMethod.human,
    )


async def test_a_catalog_label_brings_the_catalog_class(settings: Settings) -> None:
    setup_db(settings)
    deps = make_deps(settings)
    event_id = await ask_about(settings, deps)
    response = await apply_correction(CorrectionCreate(event_id=event_id, label="bagel"), deps)
    assert response.item_class is ItemClass.inventory


async def test_an_explicit_class_wins_and_is_recorded(settings: Settings) -> None:
    setup_db(settings)
    deps = make_deps(settings)
    event_id = await ask_about(settings, deps)
    response = await apply_correction(
        CorrectionCreate.model_validate(
            {"event_id": event_id, "label": "bagel", "class": "untracked"}
        ),
        deps,
    )
    assert response.item_class is ItemClass.untracked
    with session_scope() as session:
        fields = session.execute(select(Correction.field)).scalars().all()
        assert sorted(fields) == ["class", "label"]


async def test_the_second_weighing_moves_the_prior(settings: Settings) -> None:
    setup_db(settings)
    deps = make_deps(settings)
    first = await ask_about(settings, deps)
    await apply_correction(CorrectionCreate(event_id=first, label="cracked phone"), deps)

    with session_scope() as session:
        second = make_event(session, mass_g=200.0, status=EventStatus.asking).id
    await apply_correction(CorrectionCreate(event_id=second, label="cracked phone"), deps)

    with session_scope() as session:
        row = session.execute(
            select(CatalogItem).where(CatalogItem.label == "cracked phone")
        ).scalars().one()
        assert row.mass_prior_n == 2
        assert row.mass_prior_mean_g == pytest.approx(190.0)


async def test_overruling_a_confident_answer_is_counted(settings: Settings) -> None:
    setup_db(settings)
    deps = make_deps(settings)
    name = write_crop(settings, "crop-confident.jpg", CROP)
    with session_scope() as session:
        event_id = make_event(session, mass_g=95.0, crop=name).id
    get_expect_queue().push("bagel")
    assert (await identify_event(event_id, CROP, [], 95.0, 2.0, deps)).final is True

    with session_scope() as session:
        opened = open_round(session)
        assert opened is not None and opened.n_correct_first_try == 1

    await apply_correction(CorrectionCreate(event_id=event_id, label="cookie"), deps)

    with session_scope() as session:
        rnd = open_round(session)
        assert rnd is not None
        assert rnd.n_corrected_after_confident == 1
        assert rnd.n_correct_first_try == 0
        old = session.execute(
            select(Correction).where(Correction.field == "label")
        ).scalars().one()
        assert old.old_value == "bagel"
        assert old.new_value == "cookie"


async def test_an_unknown_ticket_is_refused(settings: Settings) -> None:
    setup_db(settings)
    with pytest.raises(CorrectionRefusedError, match="does not exist"):
        await apply_correction(
            CorrectionCreate(event_id=404, label="bagel"), make_deps(settings)
        )


async def test_a_ticket_that_was_never_identified_is_refused(settings: Settings) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(session, status=EventStatus.detected).id
    with pytest.raises(CorrectionRefusedError, match="not waiting"):
        await apply_correction(
            CorrectionCreate(event_id=event_id, label="bagel"), make_deps(settings)
        )


async def test_a_missing_crop_file_costs_the_exemplar_and_nothing_else(
    settings: Settings,
) -> None:
    setup_db(settings)
    with session_scope() as session:
        event_id = make_event(
            session, status=EventStatus.asking, crop="not-on-disk.jpg", mass_g=95.0
        ).id
    response = await apply_correction(
        CorrectionCreate(event_id=event_id, label="bagel"), make_deps(settings)
    )
    assert response.status is EventStatus.confirmed
    with session_scope() as session:
        assert session.execute(select(Exemplar)).scalars().all() == []
        settled = session.get(Event, event_id)
        assert settled is not None and settled.status is EventStatus.confirmed
