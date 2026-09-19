"""The close endpoints: run one, read it back, and the latest one the page opens on."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import session_scope
from app.ledger import close as close_module
from tests.test_close_fixtures import (
    PERIOD_END,
    PERIOD_START,
    build_clean_scenario,
    delete_event,
)

BODY = {"period_start": PERIOD_START, "period_end": PERIOD_END}


def test_a_clean_close_comes_back_whole(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)

    response = client.post("/api/close", json=BODY)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == close_module.STATUS_CLEAN
    assert body["period_start"] == PERIOD_START
    assert [check["result"] for check in body["checks"]] == ["pass"] * 5
    assert body["investigation_md"] is None
    assert body["totals"]["write_offs"]["total_cents"] == 3185
    assert body["totals"]["sustainability"]["title"] == close_module.SUSTAINABILITY_TITLE
    # The report carries everything the page draws, checks included.
    assert body["report"]["totals"] == body["totals"]
    assert len(body["report"]["checks"]) == 5


def test_a_broken_close_carries_the_note(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        scenario = build_clean_scenario(session)
    with session_scope() as session:
        delete_event(session, scenario.toss_ids[2])

    body = client.post("/api/close", json=BODY).json()
    assert body["status"] == close_module.STATUS_NEEDS_REVIEW
    checks = {check["id"]: check for check in body["checks"]}
    assert checks["mass_conservation"]["result"] == "fail"
    assert "250 g" in body["investigation_md"]
    investigation = body["report"]["investigation"]
    assert investigation["provider"] == "stub"
    assert investigation["review_event_ids"]
    assert body["report"]["review_event_ids"] == investigation["review_event_ids"]


def test_a_close_reads_back_by_id(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    created = client.post("/api/close", json=BODY).json()

    again = client.get(f"/api/close/{created['id']}")
    assert again.status_code == 200
    assert again.json() == created


def test_the_latest_close_is_the_newest_one(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        build_clean_scenario(session)
    client.post("/api/close", json=BODY)
    second = client.post("/api/close", json=BODY).json()

    latest = client.get("/api/close/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == second["id"]


def test_no_close_yet_says_so_plainly(client: TestClient, settings: Settings) -> None:
    response = client.get("/api/close/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "No close has been run yet."


def test_a_close_that_does_not_exist_says_so_plainly(
    client: TestClient,
    settings: Settings,
) -> None:
    response = client.get("/api/close/404")
    assert response.status_code == 404
    assert response.json()["detail"] == "That close report does not exist."


def test_an_empty_period_still_closes(client: TestClient, settings: Settings) -> None:
    response = client.post(
        "/api/close", json={"period_start": "2026-10-01", "period_end": "2026-10-02"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["events"]["tosses"] == 0
    assert body["status"] == close_module.STATUS_CLEAN
