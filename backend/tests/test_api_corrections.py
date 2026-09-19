"""POST /api/corrections over HTTP, the way the dashboard and the phone send it."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.models import EventStatus, Exemplar, Identification, IdentifyMethod
from tests.test_identify_support import make_event, make_jpeg, write_crop

CROP = make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200))


def test_an_answer_settles_the_ticket(client: TestClient, settings: Settings) -> None:
    name = write_crop(settings, "crop-api.jpg", CROP)
    with session_scope() as session:
        event_id = make_event(session, status=EventStatus.asking, crop=name, mass_g=180.0).id

    response = client.post(
        "/api/corrections", json={"event_id": event_id, "label": "Cracked  Phone"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "cracked phone"
    assert body["status"] == "confirmed"
    assert body["class"] == "untracked"

    with session_scope() as session:
        row = session.execute(
            select(Identification).where(Identification.is_final.is_(True))
        ).scalars().one()
        assert row.method is IdentifyMethod.human
        assert session.execute(select(Exemplar)).scalars().all() != []


def test_a_class_can_be_sent_with_the_answer(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        event_id = make_event(session, status=EventStatus.asking).id
    response = client.post(
        "/api/corrections",
        json={"event_id": event_id, "label": "old monitor", "class": "fixed_asset"},
    )
    assert response.status_code == 200
    assert response.json()["class"] == "fixed_asset"


def test_a_hostile_answer_never_reaches_the_handler(client: TestClient) -> None:
    response = client.post(
        "/api/corrections", json={"event_id": 1, "label": "<script>alert(1)</script>"}
    )
    assert response.status_code == 422


def test_an_unknown_ticket_says_so_in_plain_words(client: TestClient) -> None:
    response = client.post("/api/corrections", json={"event_id": 9999, "label": "bagel"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail == "That ticket does not exist."
    assert "Lane" not in detail


def test_a_ticket_that_is_not_waiting_is_refused(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        event_id = make_event(session, status=EventStatus.detected).id
    response = client.post("/api/corrections", json={"event_id": event_id, "label": "bagel"})
    assert response.status_code == 409
    assert response.json()["detail"] == "That ticket is not waiting for an answer."
