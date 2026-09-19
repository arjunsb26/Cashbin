"""Posting to the ledger, reading it back, and voiding an event.

The ledger builders are pure and tested in `test_ledger_journal.py`. These tests
cover the database side: that a posted entry comes back with its lines and the
account names filled in, that the trial balance agrees, and that a void reverses
rather than deletes.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.db import session_scope
from app.engine.records import (
    AssetInfo,
    ItemClass,
    ItemRecord,
    TaxMethod,
)
from app.engine.tax import TaxEffect
from app.ledger import journal, queries

EVENT_DATE = date(2026, 9, 19)

ASSET = AssetInfo(
    id=1,
    tag="BB-0002",
    description="Mechanical keyboard",
    cost_cents=12000,
    in_service_date=date(2025, 3, 15),
    book_life_months=36,
    tax_method=TaxMethod.bonus_100,
)


def _bagel() -> ItemRecord:
    return ItemRecord(
        event_id=1,
        label="bagel",
        item_class=ItemClass.inventory,
        mass_g=95.0,
        event_date=EVENT_DATE,
        material_mix={"food_waste": 1.0},
        regulatory_flags=["food"],
        cost_basis_cents=33,
    )


def _keyboard() -> ItemRecord:
    return ItemRecord(
        event_id=2,
        label="keyboard",
        item_class=ItemClass.fixed_asset,
        mass_g=685.0,
        event_date=EVENT_DATE,
        material_mix={"electronic_peripherals": 1.0},
        regulatory_flags=["electronics"],
        book_value_cents=6000,
        tax_basis_cents=0,
        asset_id=1,
    )


def _make_event(session: Session) -> int:
    """An entry points at an event, so the event has to exist first."""
    row = models.Event(kind=models.EventKind.toss, mass_g=95.0)
    session.add(row)
    session.flush()
    return int(row.id)


def _post_two_entries() -> tuple[int, int]:
    """One inventory write off and one asset disposal, on two events."""
    with session_scope() as session:
        first_event = _make_event(session)
        second_event = _make_event(session)
        toss = journal.inventory_toss(_bagel())
        assert toss is not None
        queries.post_entry(session, toss, event_id=first_event)
        queries.post_entry(
            session,
            journal.fixed_asset_disposal(_keyboard(), ASSET, proceeds_cents=0),
            event_id=second_event,
        )
        return first_event, second_event


def test_an_empty_journal_says_so_rather_than_failing(client: TestClient) -> None:
    body = client.get("/api/journal").json()
    assert body["entries"] == []
    assert body["trial_balance"] == []
    assert body["balanced"] is True


def test_two_posted_entries_come_back_balanced(client: TestClient) -> None:
    _post_two_entries()
    body = client.get("/api/journal", params={"basis": "book"}).json()
    assert len(body["entries"]) == 2
    assert body["balanced"] is True

    debit_total = sum(row["debit_cents"] for row in body["trial_balance"])
    credit_total = sum(row["credit_cents"] for row in body["trial_balance"])
    assert debit_total == credit_total == 33 + 12000

    by_account = {row["account"]: row for row in body["trial_balance"]}
    assert by_account["1200"]["account_name"] == "Inventory"
    assert by_account["1200"]["credit_cents"] == 33
    assert by_account["5100"]["debit_cents"] == 33
    assert by_account["1500"]["credit_cents"] == 12000
    assert by_account["7200"]["debit_cents"] == 6000


def test_every_line_carries_the_account_name_the_page_shows(client: TestClient) -> None:
    _post_two_entries()
    entries = client.get("/api/journal", params={"basis": "book"}).json()["entries"]
    for entry in entries:
        assert entry["lines"]
        for line in entry["lines"]:
            assert line["account_name"], line["account"]


def test_the_evidence_travels_with_the_entry(client: TestClient) -> None:
    _post_two_entries()
    entries = client.get("/api/journal", params={"basis": "book"}).json()["entries"]
    evidence = entries[0]["evidence"]
    assert evidence["label"] == "bagel"
    assert evidence["mass_g"] == 95.0
    assert evidence["event_id"] == entries[0]["event_id"]


def test_the_tax_memo_is_a_separate_basis(client: TestClient) -> None:
    with session_scope() as session:
        event_id = _make_event(session)
        record = _keyboard()
        effect = TaxEffect(deduction_cents=0, rule_ids=("ABANDON", "BONUS_100"))
        queries.post_entry(
            session, journal.tax_memo(record, ASSET, effect), event_id=event_id
        )

    book = client.get("/api/journal", params={"basis": "book"}).json()
    assert book["entries"] == []

    memo = client.get("/api/journal", params={"basis": "tax_memo"}).json()
    assert len(memo["entries"]) == 1
    assert memo["balanced"] is True
    evidence = memo["entries"][0]["evidence"]
    assert evidence["tax_basis_cents"] == 0
    assert evidence["book_value_cents"] == 6000
    assert evidence["book_minus_tax_cents"] == 6000


def test_no_basis_shows_every_entry(client: TestClient) -> None:
    _post_two_entries()
    with session_scope() as session:
        event_id = _make_event(session)
        effect = TaxEffect(deduction_cents=0)
        queries.post_entry(
            session, journal.tax_memo(_keyboard(), ASSET, effect), event_id=event_id
        )
    body = client.get("/api/journal").json()
    assert len(body["entries"]) == 3
    assert body["balanced"] is True


def test_voiding_an_event_reverses_it_and_deletes_nothing(client: TestClient) -> None:
    first_event, _ = _post_two_entries()
    with session_scope() as session:
        reversed_ids = queries.void_event(session, first_event)
    assert len(reversed_ids) == 1

    body = client.get("/api/journal", params={"basis": "book"}).json()
    assert len(body["entries"]) == 3
    assert body["balanced"] is True

    by_account = {row["account"]: row for row in body["trial_balance"]}
    # The write off and its reversal cancel out without either row disappearing.
    assert by_account["1200"]["debit_cents"] == 33
    assert by_account["1200"]["credit_cents"] == 33
    assert by_account["5100"]["debit_cents"] == 33
    assert by_account["5100"]["credit_cents"] == 33


def test_voiding_twice_does_not_undo_the_void(client: TestClient) -> None:
    first_event, _ = _post_two_entries()
    with session_scope() as session:
        assert len(queries.void_event(session, first_event)) == 1
    with session_scope() as session:
        assert queries.void_event(session, first_event) == []
    assert len(client.get("/api/journal").json()["entries"]) == 3


def test_voiding_an_event_with_no_entries_is_quiet(client: TestClient) -> None:
    with session_scope() as session:
        assert queries.void_event(session, 4242) == []


def test_entries_can_be_read_back_for_one_event(client: TestClient) -> None:
    _, second_event = _post_two_entries()
    with session_scope() as session:
        only = queries.list_entries(session, None, event_id=second_event)
    assert len(only) == 1
    assert only[0].memo.startswith("Dispose of")


def test_an_unbalanced_entry_never_reaches_the_database(client: TestClient) -> None:
    bad = journal.JournalEntry(
        memo="Broken",
        lines=[journal.JournalLine(account=journal.Account.cash, debit_cents=100)],
    )
    with session_scope() as session:
        event_id = _make_event(session)
        try:
            queries.post_entry(session, bad, event_id=event_id)
        except journal.Unbalanced:
            pass
        else:  # pragma: no cover - the point of the test
            raise AssertionError("an unbalanced entry was accepted")
    assert client.get("/api/journal").json()["entries"] == []
