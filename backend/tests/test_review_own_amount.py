"""Approving a value at your own amount instead of the model's.

The user's words are "for amts to approve you might wanna enter ur own amt so add that as
an option". So a person approving an estimate can type a figure, and what they typed
becomes the figure on the books: the estimate row takes it with the person as its source,
and anything posted at the old figure is reversed and posted again at the new one.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.config import Settings
from app.db import session_scope
from app.engine.records import ItemClass as EngineItemClass
from app.engine.records import ItemRecord as EngineItemRecord
from app.ledger import journal, queries, review
from tests.test_ledger_review import DAY, _donation_ticket, _event, _record

APPROVED = 62_000


def _estimate_ticket(settings: Settings) -> tuple[int, int]:
    """An inventory ticket priced entirely off a model estimate, written off at that price.

    The item is above the register limit, so the queue asks a person about it, and the one
    entry posted for it carries the estimate on both of its lines.
    """
    with session_scope() as session:
        event = _event(session)
        _record(
            session,
            event.id,
            label="espresso machine",
            item_class=models.ItemClass.inventory,
            cost_basis_cents=80_000,
            fmv_mid=80_000,
            fmv_source=review.MODEL_ESTIMATE_SOURCE,
        )
        entry = journal.inventory_toss(
            EngineItemRecord.model_validate(
                {
                    "event_id": event.id,
                    "label": "espresso machine",
                    "class": EngineItemClass.inventory,
                    "mass_g": 100.0,
                    "event_date": DAY,
                    "cost_basis_cents": 80_000,
                }
            )
        )
        assert entry is not None
        queries.post_entry(session, entry, event_id=event.id)
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        assert [row.kind for row in made] == [models.ReviewKind.estimate_above_threshold]
        return made[0].id, event.id


def _unrecorded_ticket(settings: Settings) -> tuple[int, int]:
    """Something untracked and valuable that no register row knew about."""
    with session_scope() as session:
        event = _event(session)
        _record(
            session,
            event.id,
            label="office chair",
            item_class=models.ItemClass.untracked,
            cost_basis_cents=0,
            fmv_mid=80_000,
            fmv_source=review.MODEL_ESTIMATE_SOURCE,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        assert [row.kind for row in made] == [models.ReviewKind.possible_unrecorded_asset]
        return made[0].id, event.id


# The estimate row -----------------------------------------------------------


def test_approving_at_your_own_amount_puts_it_on_the_estimate(settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    with session_scope() as session:
        _item, _reversing, difference, detail = review.approve(
            session, item_id, "nishad", "", APPROVED
        )
        session.commit()

    assert difference == APPROVED - 80_000
    assert detail.startswith("Approved at $620.00, the estimate said $800.00.")

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == APPROVED
    assert record.fmv_source == review.PERSON_SOURCE


def test_the_same_amount_changes_nothing(settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    with session_scope() as session:
        before = len(queries.list_entries(session, event_id=event_id))
        _item, reversing, difference, detail = review.approve(
            session, item_id, "nishad", "", 80_000
        )
        session.commit()
        after = len(queries.list_entries(session, event_id=event_id))

    assert reversing == []
    assert difference == 0
    assert "stand as they are" in detail
    assert before == after

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_source == review.MODEL_ESTIMATE_SOURCE


def test_no_amount_at_all_changes_nothing(settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    with session_scope() as session:
        _item, reversing, difference, detail = review.approve(session, item_id, "nishad", "")
        session.commit()

    assert reversing == []
    assert difference == 0
    assert "stand as they are" in detail

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == 80_000
    assert record.fmv_source == review.MODEL_ESTIMATE_SOURCE


def test_an_unrecorded_asset_takes_the_new_amount_too(settings: Settings) -> None:
    item_id, event_id = _unrecorded_ticket(settings)

    with session_scope() as session:
        _item, reversing, difference, _detail = review.approve(
            session, item_id, "nishad", "", APPROVED
        )
        session.commit()

    # Nothing was posted for an untracked thing, so there is nothing to reverse.
    assert reversing == []
    assert difference == APPROVED - 80_000

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == APPROVED
    assert record.fmv_source == review.PERSON_SOURCE


def test_a_donation_ignores_the_amount(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()
        item_id = made[0].id

    with session_scope() as session:
        _item, reversing, difference, detail = review.approve(
            session, item_id, "nishad", "", APPROVED
        )
        session.commit()

    assert reversing == []
    assert difference == 0
    assert "stand as they are" in detail

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == 300


# The ledger -----------------------------------------------------------------


def test_the_posted_entry_is_reversed_and_reposted_at_the_new_amount(
    settings: Settings,
) -> None:
    item_id, event_id = _estimate_ticket(settings)

    with session_scope() as session:
        _item, reversing, _difference, detail = review.approve(
            session, item_id, "nishad", "", APPROVED
        )
        session.commit()

    assert len(reversing) == 1
    assert "reposted" in detail

    with session_scope() as session:
        entries = queries.list_entries(session, event_id=event_id)
        rows = queries.trial_balance(session)

    # The original, its reversal, and the same entry again at the approved figure.
    assert len(entries) == 3
    assert entries[1].memo.startswith("Reversal of: ")
    restated = entries[2]
    assert restated.evidence["restated_from_cents"] == 80_000
    assert {line.debit_cents + line.credit_cents for line in restated.lines} == {APPROVED}

    assert sum(row.debit_cents for row in rows) == sum(row.credit_cents for row in rows)
    waste = next(row for row in rows if row.account == "5100")
    assert waste.debit_cents - waste.credit_cents == APPROVED


def test_the_audit_trail_says_what_was_approved(settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    with session_scope() as session:
        review.approve(session, item_id, "nishad", "", APPROVED)
        session.commit()

    with session_scope() as session:
        rows = list(
            session.scalars(
                select(models.Correction).where(models.Correction.event_id == event_id)
            )
        )
    assert [row.new_value for row in rows] == [
        "estimate_above_threshold approved at 62000 cents"
    ]


# The route ------------------------------------------------------------------


def test_the_route_takes_the_amount(client: TestClient, settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    body = client.post(
        f"/api/review/{item_id}/approve",
        json={"by": "nishad", "amount_cents": APPROVED},
    )
    assert body.status_code == 200
    found = body.json()
    assert found["difference_cents"] == APPROVED - 80_000
    assert found["detail"].startswith("Approved at $620.00, the estimate said $800.00.")
    assert len(found["reversing_entry_ids"]) == 1

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == APPROVED


def test_an_amount_outside_the_range_is_refused(
    client: TestClient, settings: Settings
) -> None:
    item_id, _event_id = _estimate_ticket(settings)
    for amount in (-1, 10_000_001):
        body = client.post(
            f"/api/review/{item_id}/approve", json={"amount_cents": amount}
        )
        assert body.status_code == 422


def test_rejecting_ignores_the_amount(client: TestClient, settings: Settings) -> None:
    item_id, event_id = _estimate_ticket(settings)

    body = client.post(
        f"/api/review/{item_id}/reject", json={"by": "nishad", "amount_cents": APPROVED}
    )
    assert body.status_code == 200

    with session_scope() as session:
        record = session.get(models.ItemRecord, event_id)
    assert record is not None
    assert record.fmv_mid == 80_000
    assert record.fmv_source == review.MODEL_ESTIMATE_SOURCE
