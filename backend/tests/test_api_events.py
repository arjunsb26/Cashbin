"""The events REST surface: list, detail, void, and the dev-only injected toss.

Lanes B and C fill the identification, option, entry and correction tables later. Every
read here has to work while they are empty, because that is the state every event is in
for its first second of life.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import Settings
from app.db import session_scope
from app.models import (
    CropQuality,
    Event,
    EventKind,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
    ItemRecord,
    JournalBasis,
    JournalEntry,
    JournalLine,
    OptionKind,
    OptionScore,
)

BAGEL = {"label": "bagel", "mass_g": 95.0}


def test_an_empty_list_is_an_empty_list(client: TestClient) -> None:
    assert client.get("/api/events").json() == {"events": []}


def show_the_camera(dev_client: TestClient) -> None:
    """Two frames in the ring, which is what an Add off the live camera needs."""
    from app.ingest.state import get_ingest
    from tests.ingest_helpers import background_frame, frame_with_item, jpeg

    deps = get_ingest(dev_client.app)  # type: ignore[arg-type]
    now = deps.clock()
    deps.frames.push(jpeg(background_frame()), now - 2000.0)
    deps.frames.push(jpeg(frame_with_item(background_frame())), now)


def test_a_missing_event_is_a_404(client: TestClient) -> None:
    response = client.get("/api/events/9999")
    assert response.status_code == 404
    assert "Lane" not in response.json()["detail"]


def test_an_injected_toss_becomes_an_event(dev_client: TestClient) -> None:
    # The glue is attached now, so an injected toss runs the whole pipeline and comes
    # back posted rather than stopping at detected. With no image in the body the frames
    # come from the camera, so one is held up first.
    show_the_camera(dev_client)
    posted = dev_client.post("/api/sim/toss", json=BAGEL)
    assert posted.status_code == 200
    body = posted.json()
    assert body["status"] == EventStatus.posted

    listed = dev_client.get("/api/events").json()["events"]
    assert len(listed) == 1
    assert listed[0]["id"] == body["event_id"]
    assert listed[0]["kind"] == EventKind.toss
    assert abs(listed[0]["mass_g"] - 95.0) < 0.01
    assert listed[0]["crop_quality"] == CropQuality.ok


def test_an_injected_toss_with_an_image_gets_a_frame(
    dev_client: TestClient, dev_settings: Settings
) -> None:
    posted = dev_client.post("/api/sim/toss", json={**BAGEL, "image": "bagel.png"})
    assert posted.status_code == 200
    event_id = posted.json()["event_id"]
    detail = dev_client.get(f"/api/events/{event_id}").json()
    # One frame in the ring is the after frame with nothing to diff against, so the
    # crop falls back and says so rather than inventing a bounding box.
    assert detail["frame_after_url"] == f"/media/{event_id}/after.jpg"
    assert detail["event"]["crop_quality"] == CropQuality.low
    assert (Path(dev_settings.media_dir) / str(event_id) / "after.jpg").stat().st_size > 0


def test_an_image_outside_the_sim_assets_is_refused(dev_client: TestClient) -> None:
    """The image name comes off the wire, so it is treated as outside text, not a path."""
    for name in ("../../backend/app/main.py", "..\\..\\.env", "/etc/passwd", "nothing.png"):
        response = dev_client.post("/api/sim/toss", json={**BAGEL, "image": name})
        assert response.status_code == 400, name
        assert "Lane" not in response.json()["detail"]
    assert dev_client.get("/api/events").json()["events"] == []


def test_the_list_is_newest_first_and_filters(dev_client: TestClient) -> None:
    for mass in (95.0, 780.0, 62.0):
        show_the_camera(dev_client)
        dev_client.post("/api/sim/toss", json={"label": "bagel", "mass_g": mass})
    listed = dev_client.get("/api/events").json()["events"]
    assert [row["mass_g"] for row in listed] == [62.0, 780.0, 95.0]

    with session_scope() as session:
        row = session.get(Event, listed[0]["id"])
        assert row is not None
        # Void, because the pipeline posts every toss it identifies and a filter test
        # needs a status only this test has set.
        row.status = EventStatus.void
        row.round_id = None

    voided = dev_client.get("/api/events", params={"status": "void"}).json()["events"]
    assert [row["id"] for row in voided] == [listed[0]["id"]]
    assert dev_client.get("/api/events", params={"round": 7}).json()["events"] == []


def test_detail_carries_the_trace_and_the_later_tables(dev_client: TestClient) -> None:
    show_the_camera(dev_client)
    event_id = dev_client.post("/api/sim/toss", json=BAGEL).json()["event_id"]

    with session_scope() as session:
        # This case reads hand made rows, so the pipeline's own rows for the same event
        # are cleared first rather than fought with.
        for table in (Identification, ItemRecord, OptionScore):
            session.execute(delete(table).where(table.event_id == event_id))
        session.add(
            Identification(
                event_id=event_id,
                method=IdentifyMethod.stub,
                label="bagel",
                item_class=ItemClass.inventory,
                confidence=0.91,
                candidates_json='[{"label": "bagel", "p": 0.91}]',
                posterior_json='{"bagel": 0.91}',
                is_final=True,
                provider="stub",
                model="none",
            )
        )
        session.add(
            ItemRecord(
                event_id=event_id,
                label="bagel",
                item_class=ItemClass.inventory,
                mass_g=95.0,
                condition="unknown",
                book_value_cents=120,
            )
        )
        session.add(
            OptionScore(
                event_id=event_id,
                option=OptionKind.trash,
                allowed=True,
                net_after_tax_cents=-120,
                rank=2,
            )
        )
        session.add(
            OptionScore(
                event_id=event_id,
                option=OptionKind.donate,
                allowed=True,
                net_after_tax_cents=80,
                rank=1,
            )
        )
        entry = JournalEntry(event_id=event_id, memo="bagel", basis=JournalBasis.book)
        session.add(entry)
        session.flush()
        session.add(JournalLine(entry_id=entry.id, account="5100", debit_cents=120))
        session.add(JournalLine(entry_id=entry.id, account="1200", credit_cents=120))

    detail = dev_client.get(f"/api/events/{event_id}").json()
    assert len(detail["trace"]) > 10
    assert detail["trace"][0][0] < detail["trace"][-1][0]
    assert len(detail["identifications"]) == 1
    assert detail["identifications"][0]["provider"] == "stub"
    assert detail["identifications"][0]["candidates"] == [{"label": "bagel", "p": 0.91}]
    assert detail["item_record"]["label"] == "bagel"
    assert len(detail["options"]) == 2
    assert len(detail["entries"][0]["lines"]) == 2
    assert detail["corrections"] == []

    summary = detail["event"]
    assert summary["label"] == "bagel"
    assert summary["class"] == ItemClass.inventory
    assert summary["net_book_cents"] == 120
    assert summary["best_option"] == OptionKind.donate
    # PLAN.md section 10 item 4: what following the best option beats binning it by.
    assert summary["saved_if_followed_cents"] == 200


def test_a_bad_json_column_does_not_take_the_read_down(dev_client: TestClient) -> None:
    show_the_camera(dev_client)
    event_id = dev_client.post("/api/sim/toss", json=BAGEL).json()["event_id"]
    with session_scope() as session:
        row = session.get(Event, event_id)
        assert row is not None
        row.trace_json = "{not json at all"
    detail = dev_client.get(f"/api/events/{event_id}").json()
    assert detail["trace"] == []


def test_void_marks_the_event_and_says_what_was_reversed(dev_client: TestClient) -> None:
    show_the_camera(dev_client)
    event_id = dev_client.post("/api/sim/toss", json=BAGEL).json()["event_id"]
    response = dev_client.post(f"/api/events/{event_id}/void")
    assert response.status_code == 200
    assert response.json() == {
        "event_id": event_id,
        "status": EventStatus.void,
        "reversing_entry_ids": [],
    }
    assert dev_client.get(f"/api/events/{event_id}").json()["event"]["status"] == EventStatus.void
    assert dev_client.get("/api/events", params={"status": "void"}).json()["events"]


def test_voiding_something_that_is_not_there_is_a_404(client: TestClient) -> None:
    assert client.post("/api/events/404/void").status_code == 404


def test_the_sim_route_is_not_in_the_demo_build(client: TestClient) -> None:
    assert client.post("/api/sim/toss", json=BAGEL).status_code == 404


def test_an_event_is_marked_an_estimate_when_the_value_came_from_a_model(
    dev_client: TestClient,
) -> None:
    """PLAN.md 21a item 18. The tape marks a model figure so nobody reads it as measured."""
    dev_client.post("/api/sim/expect", json={"label": "bagel"})
    show_the_camera(dev_client)
    event_id = dev_client.post("/api/sim/toss", json=BAGEL).json()["event_id"]

    listed = dev_client.get("/api/events").json()["events"]
    assert listed[0]["is_estimate"] is False

    with session_scope() as session:
        record = session.get(ItemRecord, event_id)
        assert record is not None
        record.fmv_source = "model_estimate"

    marked = dev_client.get("/api/events").json()["events"]
    assert marked[0]["is_estimate"] is True
    assert dev_client.get(f"/api/events/{event_id}").json()["event"]["is_estimate"] is True


def test_the_ticket_names_every_account_it_posted_to(client: TestClient) -> None:
    """The evidence drawer draws T-accounts. A bare code teaches nobody anything."""
    from app.db import session_scope
    from app.ledger import queries
    from app.ledger.journal import Account, Basis, JournalEntry, JournalLine

    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=95.0, status=EventStatus.posted)
        session.add(event)
        session.flush()
        event_id = int(event.id)
        queries.post_entry(
            session,
            JournalEntry(
                memo="Write off bagel",
                basis=Basis.book,
                lines=[
                    JournalLine(account=Account.waste_and_shrink, debit_cents=33),
                    JournalLine(account=Account.inventory, credit_cents=33),
                ],
            ),
            event_id=event_id,
        )

    lines = client.get(f"/api/events/{event_id}").json()["entries"][0]["lines"]
    named = {line["account"]: line["account_name"] for line in lines}
    assert named == {"5100": "Waste and Shrink Expense", "1200": "Inventory"}


def test_the_ticket_says_what_the_journal_actually_posted(client: TestClient) -> None:
    """`net_book_cents` is a book value. The tape wants the amount that hit the books."""
    from app.ledger import queries
    from app.ledger.journal import Account, Basis, JournalEntry, JournalLine

    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=95.0, status=EventStatus.posted)
        session.add(event)
        session.flush()
        event_id = int(event.id)
        queries.post_entry(
            session,
            JournalEntry(
                memo="Write off bagel",
                basis=Basis.book,
                lines=[
                    JournalLine(account=Account.waste_and_shrink, debit_cents=33),
                    JournalLine(account=Account.inventory, credit_cents=33),
                ],
            ),
            event_id=event_id,
        )

    summary = client.get(f"/api/events/{event_id}").json()["event"]
    assert summary["posted_cents"] == -33


def test_a_ticket_that_posted_nothing_says_nothing_rather_than_zero(
    client: TestClient,
) -> None:
    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=95.0, status=EventStatus.identified)
        session.add(event)
        session.flush()
        event_id = int(event.id)

    summary = client.get(f"/api/events/{event_id}").json()["event"]
    assert summary["posted_cents"] is None


def test_a_gain_on_the_books_reads_as_a_positive_amount(client: TestClient) -> None:
    from app.ledger import queries
    from app.ledger.journal import Account, Basis, JournalEntry, JournalLine

    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=780.0, status=EventStatus.posted)
        session.add(event)
        session.flush()
        event_id = int(event.id)
        queries.post_entry(
            session,
            JournalEntry(
                memo="Dispose of keyboard",
                basis=Basis.book,
                lines=[
                    JournalLine(account=Account.cash, debit_cents=500),
                    JournalLine(account=Account.gain_on_disposal, credit_cents=500),
                ],
            ),
            event_id=event_id,
        )

    summary = client.get(f"/api/events/{event_id}").json()["event"]
    assert summary["posted_cents"] == 500


def test_a_valuable_untracked_thing_is_flagged_on_the_ticket(
    client: TestClient, settings: Settings
) -> None:
    """The close already raises this. The ticket is where a person would act on it."""
    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=200.0, status=EventStatus.posted)
        session.add(event)
        session.flush()
        event_id = int(event.id)
        session.add(
            ItemRecord(
                event_id=event_id,
                label="phone",
                item_class=ItemClass.untracked,
                mass_g=200.0,
                fmv_mid=settings.capitalization_threshold_cents + 1,
            )
        )

    summary = client.get(f"/api/events/{event_id}").json()["event"]
    assert summary["flags"] == ["possible_unrecorded_asset"]


def test_a_cheap_untracked_thing_carries_no_flag(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        event = Event(kind=EventKind.toss, mass_g=12.0, status=EventStatus.posted)
        session.add(event)
        session.flush()
        event_id = int(event.id)
        session.add(
            ItemRecord(
                event_id=event_id,
                label="water bottle empty",
                item_class=ItemClass.untracked,
                mass_g=12.0,
                fmv_mid=50,
            )
        )

    summary = client.get(f"/api/events/{event_id}").json()["event"]
    assert summary["flags"] == []
