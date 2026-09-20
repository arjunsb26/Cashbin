"""M3 on the wire: the tagged keyboard, the bagel and the two electronics.

PLAN.md section 20 M3. The whole demo goes in through `/ws/bin` with the camera feeding
`/ws/phone`'s ring on the same clock, and what comes back is read off the REST surface and
off the phone channel, not out of a function call.

The one register row this needs is created through `POST /api/assets` inside the test.
`backend/data/assets_seed.csv` still says `NEEDS_HUMAN` for every price and date, which is
correct: those are the team's real numbers and nobody but the team may fill them in.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import session_scope
from app.main import create_app
from app.models import (
    Asset,
    AssetStatus,
    EventKind,
    EventStatus,
    JournalBasis,
    OptionKind,
    TaxMethod,
)
from tests.test_pipeline_e2e import (
    KEYBOARD_COST_CENTS,
    KEYBOARD_LIFE_MONTHS,
    KEYBOARD_TAG,
    demo_settings,  # noqa: F401  (a fixture, used by name below)
    run_demo,
)

# The register row the demo needs, in the shape `POST /api/assets` takes it. Bought after
# 19 January 2025 and expensed in full, so the book column and the tax column differ.


def keyboard_row() -> dict[str, Any]:
    today = date.today()
    return {
        "tag": KEYBOARD_TAG,
        "description": "Mechanical keyboard",
        "category": "peripheral",
        "cost_cents": KEYBOARD_COST_CENTS,
        "in_service_date": today.replace(year=today.year - 1).isoformat(),
        "book_life_months": KEYBOARD_LIFE_MONTHS,
        "salvage_cents": 0,
        "tax_method": TaxMethod.bonus_100,
    }


def seed_through_the_api(client: TestClient) -> None:
    """The catalog and register from the seed files, with the keyboard row set over REST.

    The seed file's own figures are approximate and the user may change them again, so this
    case writes the numbers its assertions depend on through `PATCH /api/assets/{id}` rather
    than reading whatever the CSV happens to hold today. Nothing is written back to the CSV.
    """
    seed_the_files()
    row = keyboard_row()
    existing = next(
        (
            asset
            for asset in client.get("/api/assets").json()["assets"]
            if asset["tag"] == KEYBOARD_TAG
        ),
        None,
    )
    if existing is None:
        written = client.post("/api/assets", json=row)
        assert written.status_code == 201, written.text
    else:
        written = client.patch(f"/api/assets/{existing['id']}", json=row)
        assert written.status_code == 200, written.text
    assert written.json()["tag"] == KEYBOARD_TAG
    assert written.json()["status"] == AssetStatus.active


def seed_the_files() -> None:
    """The catalog and the register, exactly as a first start loads them."""
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scripts.seed_db import seed_all

    with session_scope() as session:
        seed_all(session)


def test_the_m3_story_reads_off_the_api_and_the_phone(
    demo_settings: Settings,  # noqa: F811
) -> None:
    app = create_app(demo_settings)
    with TestClient(app) as client:
        seed_through_the_api(client)
        seen = run_demo(client, app)

        rows = client.get("/api/events").json()["events"]
        tosses = [row for row in rows if row["kind"] == EventKind.toss]
        assert {row["status"] for row in tosses} == {EventStatus.posted}
        by_label = {row["label"]: row for row in tosses}

        # 1. The tagged keyboard: a book loss, a tax basis of zero, two entries, off the
        # register.
        keyboard = by_label["mechanical keyboard"]
        assert keyboard["class"] == "fixed_asset"
        detail = client.get(f"/api/events/{keyboard['id']}").json()
        record = detail["item_record"]
        assert record["book_value_cents"] > 0
        assert record["tax_basis_cents"] == 0
        assert keyboard["net_book_cents"] == record["book_value_cents"]

        entries = {entry["basis"]: entry for entry in detail["entries"]}
        assert JournalBasis.book in entries
        assert JournalBasis.tax_memo in entries
        book_accounts = {line["account"] for line in entries[JournalBasis.book]["lines"]}
        assert "1500" in book_accounts, "the asset has to come off Fixed Assets"
        assert "1590" in book_accounts, "accumulated depreciation has to come off with it"
        assert "7200" in book_accounts, "the remaining book value is the loss on disposal"

        trash = next(
            row for row in detail["options"] if row["option"] == OptionKind.trash
        )
        assert "BONUS_100" in trash["rule_ids"]
        assert "ABANDON" in trash["rule_ids"]

        assets = client.get("/api/assets").json()["assets"]
        tagged = next(row for row in assets if row["tag"] == KEYBOARD_TAG)
        assert tagged["status"] == AssetStatus.disposed
        assert tagged["disposed_event_id"] == keyboard["id"]
        with session_scope() as session:
            stored = session.query(Asset).filter(Asset.tag == KEYBOARD_TAG).one()
            assert stored.status is AssetStatus.disposed

        # 2. The bagel: donating beats binning, and a person has to sign it off.
        bagel = client.get(f"/api/events/{by_label['bagel']['id']}").json()
        ranked = {row["option"]: row["rank"] for row in bagel["options"] if row["allowed"]}
        assert ranked[OptionKind.donate] < ranked[OptionKind.trash]
        donate = next(row for row in bagel["options"] if row["option"] == OptionKind.donate)
        assert donate["needs_human_review"] is True
        assert "DONATE_FOOD" in donate["rule_ids"]
        assert by_label["bagel"]["saved_if_followed_cents"] > 0

        # 3. The charger and the phone: the landfill is closed, and the phone said so in red.
        for label in ("usb-c charger", "phone"):
            options = client.get(f"/api/events/{by_label[label]['id']}").json()["options"]
            blocked = next(row for row in options if row["option"] == OptionKind.trash)
            assert blocked["allowed"] is False
            assert blocked["blocked_reason"]
            assert "EWASTE" in blocked["rule_ids"]

        results = {result["title"].lower(): result for result in seen["results"]}
        assert results["usb-c charger"]["tone"] == "red"
        assert results["phone"]["tone"] == "red"
        assert results["bagel"]["tone"] in {"amber", "green"}
        for result in seen["results"]:
            assert result["line"], "every phone result says what to do"

        screens = {screen["l1"].lower(): screen for screen in seen["screens"]}
        assert screens["usb-c charger"]["c"] == "red"
        assert screens["phone"]["c"] == "red"
