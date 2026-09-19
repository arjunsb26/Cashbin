"""The rounds list, starting a round, and the header summary over HTTP."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import session_scope
from app.learn import rounds
from app.models import OptionKind, OptionScore
from tests.test_identify_support import make_event


def test_an_empty_system_reports_nothing_rather_than_zeroes(client: TestClient) -> None:
    rounds_body = client.get("/api/metrics/rounds").json()
    assert rounds_body == {"rounds": [], "learned": []}

    summary = client.get("/api/summary").json()
    assert summary == {
        "saved_if_followed_cents": 0,
        "kg_diverted": 0.0,
        "events": 0,
        "first_try_accuracy": None,
    }


def test_starting_a_round_returns_the_new_one(client: TestClient) -> None:
    first = client.post("/api/metrics/rounds/start")
    assert first.status_code == 200
    assert first.json()["id"] == 1
    assert first.json()["n_events"] == 0

    second = client.post("/api/metrics/rounds/start")
    assert second.json()["id"] == 2

    listed = client.get("/api/metrics/rounds").json()["rounds"]
    assert [r["id"] for r in listed] == [1, 2]
    assert listed[0]["ended_at"] is not None
    assert listed[1]["ended_at"] is None


def test_the_rounds_list_carries_the_derived_rates(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        event = make_event(session)
        rounds.record_event(
            session,
            settings,
            event=event,
            asked=True,
            confident=False,
            latency_ms=240,
            cost_microusd=800,
        )
    row = client.get("/api/metrics/rounds").json()["rounds"][0]
    assert row["n_events"] == 1
    assert row["ask_rate"] == 1.0
    assert row["first_try_accuracy"] == 0.0
    assert row["cost_per_event_microusd"] == 800.0
    assert row["mean_latency_ms"] == 240.0
    assert row["local_share"] == 0.0


def test_the_header_adds_up_the_engines_option_rows(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        event = make_event(session)
        session.add_all(
            [
                OptionScore(
                    event_id=event.id,
                    option=OptionKind.trash,
                    net_after_tax_cents=-40,
                    kg_landfill=0.2,
                    rank=2,
                ),
                OptionScore(
                    event_id=event.id,
                    option=OptionKind.resell,
                    net_after_tax_cents=310,
                    kg_landfill=0.0,
                    rank=1,
                ),
            ]
        )
    summary = client.get("/api/summary").json()
    assert summary["saved_if_followed_cents"] == 350
    assert summary["kg_diverted"] == 0.2
    assert summary["events"] == 1


async def test_the_rounds_list_carries_what_the_system_learned(
    client: TestClient, settings: Settings
) -> None:
    """The Learning page reads this list. PLAN.md section 12 asks for it in plain words."""
    from app.identify.pipeline import identify_event
    from app.identify.stub import get_expect_queue
    from app.learn.corrections import apply_correction
    from app.schemas import CorrectionCreate
    from tests.test_identify_support import make_deps, make_jpeg, write_crop

    crop = make_jpeg(colour=(60, 180, 230), patch=(40, 120, 200))
    name = write_crop(settings, "crop-learned.jpg", crop)
    deps = make_deps(settings)
    with session_scope() as session:
        event_id = make_event(session, mass_g=180.0, crop=name).id
    get_expect_queue().push("bagel")
    await identify_event(event_id, crop, [], 180.0, 2.0, deps)
    await apply_correction(CorrectionCreate(event_id=event_id, label="cracked phone"), deps)

    body = client.get("/api/metrics/rounds").json()
    assert body["learned"] == ["bagel vs cracked phone: now recognised from 1 example"]
