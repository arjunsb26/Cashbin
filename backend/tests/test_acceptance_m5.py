"""M5 on the wire: the demo closes clean, and a missing ticket is caught in grams.

PLAN.md section 20 M5. The close runs over the demo scenario through `POST /api/close`, and
every self-check passes. Then one ticket stops counting, the way a real gap appears, and
mass conservation fails with the size of the hole in its note.

Both ways of losing a ticket are covered: voiding it on the REST surface, which is what a
person does, and deleting the row outright, which is what PLAN.md section 19 asks for.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import Settings
from app.db import session_scope
from app.main import create_app
from app.models import (
    Event,
    EventKind,
    Identification,
    ItemRecord,
    JournalEntry,
    JournalLine,
    OptionScore,
)
from tests.test_acceptance_m3 import seed_through_the_api
from tests.test_pipeline_e2e import (
    demo_settings,  # noqa: F401  (a fixture, used by name below)
    run_demo,
)

CHECK_IDS = (
    "mass_conservation",
    "ledger_balance",
    "register_consistency",
    "unresolved_asks",
    "low_confidence_share",
)

# The charger. An untracked object with no journal entry behind it, so losing it is a gap in
# the mass and in nothing else, which is what this check is meant to see on its own.
LOST_TOSS_INDEX = 2


def period() -> dict[str, str]:
    """Today, in the shape `POST /api/close` takes it."""
    today = datetime.now(UTC).date().isoformat()
    return {"period_start": today, "period_end": today}


def by_id(checks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {check["id"]: check for check in checks}


def toss_ids() -> list[int]:
    with session_scope() as session:
        rows = (
            session.query(Event)
            .filter(Event.kind == EventKind.toss)
            .order_by(Event.id)
            .all()
        )
        return [int(row.id) for row in rows]


def mass_of(event_id: int) -> float:
    with session_scope() as session:
        row = session.get(Event, event_id)
        assert row is not None
        return float(row.mass_g or 0.0)


def hard_delete(event_id: int) -> None:
    """Take the row out of the database entirely, dependants first."""
    with session_scope() as session:
        entry_ids = [
            int(row_id)
            for row_id in session.scalars(
                JournalEntry.__table__.select()
                .with_only_columns(JournalEntry.id)
                .where(JournalEntry.event_id == event_id)
            )
        ]
        if entry_ids:
            session.execute(delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids)))
            session.execute(delete(JournalEntry).where(JournalEntry.event_id == event_id))
        session.execute(delete(OptionScore).where(OptionScore.event_id == event_id))
        session.execute(delete(Identification).where(Identification.event_id == event_id))
        session.execute(delete(ItemRecord).where(ItemRecord.event_id == event_id))
        session.execute(delete(Event).where(Event.id == event_id))


def assert_the_gap_is_named(check: dict[str, Any], missing_g: float) -> float:
    """A failed conservation check says how many grams are unaccounted for."""
    assert check["result"] == "fail"
    gap_g = abs(float(check["numbers"]["difference_g"]))
    # The gap is the lost ticket, inside the same measurement band the check itself uses.
    # A clean close already carries a gram or so of scale noise, and that noise does not
    # go away when a ticket does.
    band_g = float(check["numbers"]["tolerance_g"])
    assert abs(gap_g - missing_g) <= band_g, "the gap has to be the ticket that went missing"
    assert f"{gap_g:,.0f} g" in check["detail"]
    assert "a toss was never ticketed" in check["detail"]
    return gap_g


def close_the_demo(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/close", json=period())
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_the_demo_closes_clean(demo_settings: Settings) -> None:  # noqa: F811
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_through_the_api(client)
        run_demo(client, app)

        body = close_the_demo(client)
        checks = by_id(body["checks"])
        assert set(checks) == set(CHECK_IDS)
        failed = [check["id"] for check in body["checks"] if check["result"] != "pass"]
        assert failed == [], json.dumps(body["checks"], indent=2)
        assert body["status"] == "clean"
        assert body["totals"]
        mass = checks["mass_conservation"]
        assert mass["numbers"]["tickets"] == 4
        assert abs(mass["numbers"]["difference_g"]) <= mass["numbers"]["tolerance_g"]
        # A clean close has nothing to investigate.
        assert not body["investigation_md"]


def test_voiding_a_ticket_makes_mass_conservation_fail(
    demo_settings: Settings,  # noqa: F811
) -> None:
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_through_the_api(client)
        run_demo(client, app)
        assert close_the_demo(client)["status"] == "clean"

        lost = toss_ids()[LOST_TOSS_INDEX]
        missing_g = mass_of(lost)
        voided = client.post(f"/api/events/{lost}/void")
        assert voided.status_code == 200

        body = close_the_demo(client)
        checks = by_id(body["checks"])
        assert checks["mass_conservation"]["numbers"]["tickets"] == 3
        gap_g = assert_the_gap_is_named(checks["mass_conservation"], missing_g)
        assert gap_g > 0
        assert body["status"] != "clean"
        assert body["investigation_md"], "a failed check has to come with a note"


def test_deleting_a_ticket_makes_mass_conservation_fail(
    demo_settings: Settings,  # noqa: F811
) -> None:
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_through_the_api(client)
        run_demo(client, app)
        assert close_the_demo(client)["status"] == "clean"

        lost = toss_ids()[LOST_TOSS_INDEX]
        missing_g = mass_of(lost)
        hard_delete(lost)

        body = close_the_demo(client)
        checks = by_id(body["checks"])
        assert checks["mass_conservation"]["numbers"]["tickets"] == 3
        assert_the_gap_is_named(checks["mass_conservation"], missing_g)
        assert body["status"] != "clean"
        assert body["investigation_md"]
