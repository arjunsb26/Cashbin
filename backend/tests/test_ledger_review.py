"""The review queue: what it raises, and what approving or rejecting actually does."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import session_scope
from app.engine.records import AssetInfo, AssetStatus, ItemClass, TaxMethod
from app.engine.records import ItemRecord as EngineItemRecord
from app.ledger import journal, queries, review

DAY = "2026-09-19"


def _ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


def _event(
    session: Session,
    *,
    mass_g: float = 100.0,
    status: models.EventStatus = models.EventStatus.posted,
    created_at: str | None = None,
) -> models.Event:
    row = models.Event(
        created_at=created_at or f"{DAY}T12:00:00+00:00",
        kind=models.EventKind.toss,
        mass_g=mass_g,
        mass_err_g=1.0,
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def _record(
    session: Session,
    event_id: int,
    *,
    label: str = "bagel",
    item_class: models.ItemClass = models.ItemClass.inventory,
    cost_basis_cents: int = 100,
    fmv_mid: int | None = None,
    fmv_source: str | None = None,
    book_value_cents: int = 0,
    tax_basis_cents: int = 0,
    asset_id: int | None = None,
) -> models.ItemRecord:
    row = models.ItemRecord(
        event_id=event_id,
        label=label,
        item_class=item_class,
        mass_g=100.0,
        condition="unknown",
        material_mix_json=json.dumps({"food_waste": 1.0}),
        regulatory_flags_json=json.dumps(["food"]),
        book_value_cents=book_value_cents,
        tax_basis_cents=tax_basis_cents,
        cost_basis_cents=cost_basis_cents,
        fmv_mid=fmv_mid,
        fmv_source=fmv_source,
        asset_id=asset_id,
    )
    session.add(row)
    session.flush()
    return row


def _option(
    session: Session,
    event_id: int,
    option: models.OptionKind,
    net: int,
    *,
    needs_human_review: bool = False,
    rank: int | None = None,
    kg_co2e: float | None = 0.1,
) -> models.OptionScore:
    row = models.OptionScore(
        event_id=event_id,
        option=option,
        allowed=True,
        cash_cents=net,
        tax_effect_cents=0,
        net_after_tax_cents=net,
        kg_co2e=kg_co2e,
        kg_landfill=0.1,
        needs_human_review=needs_human_review,
        notes_json=json.dumps([]),
        rule_ids_json=json.dumps(["DONATE_FOOD"] if needs_human_review else []),
        rank=rank,
    )
    session.add(row)
    session.flush()
    return row


def _donation_ticket(session: Session) -> int:
    """A bagel worth more donated than binned, which a person has to sign off."""
    event = _event(session)
    _record(session, event.id, label="bagel", cost_basis_cents=100, fmv_mid=300)
    _option(session, event.id, models.OptionKind.trash, -2, rank=2)
    _option(
        session, event.id, models.OptionKind.donate, 60, needs_human_review=True, rank=1,
        kg_co2e=0.01,
    )
    entry = journal.inventory_toss(
        EngineItemRecord.model_validate(
            {
                "event_id": event.id,
                "label": "bagel",
                "class": ItemClass.inventory,
                "mass_g": 100.0,
                "event_date": DAY,
                "cost_basis_cents": 100,
            }
        )
    )
    assert entry is not None
    queries.post_entry(session, entry, event_id=event.id)
    session.commit()
    return event.id


def test_a_donation_best_option_raises_one_item(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()

    assert [row.kind for row in made] == [models.ReviewKind.donation]
    assert made[0].amount_cents == 62
    assert "sign it off" in made[0].reason


def test_the_same_ticket_twice_raises_nothing_new(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        review.create_for_event(session, event_id, settings)
        session.commit()
    with session_scope() as session:
        again = review.create_for_event(session, event_id, settings)
        session.commit()
    assert again == []
    with session_scope() as session:
        assert review.open_count(session) == 1


def test_an_untracked_valuable_thing_is_a_possible_unrecorded_asset(
    settings: Settings,
) -> None:
    with session_scope() as session:
        event = _event(session)
        _record(
            session,
            event.id,
            label="office chair",
            item_class=models.ItemClass.untracked,
            cost_basis_cents=0,
            fmv_mid=80_000,
            fmv_source="model_estimate",
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()

    # Both tests look at the same figure. The sharper question wins and only one
    # item is raised.
    assert [row.kind for row in made] == [models.ReviewKind.possible_unrecorded_asset]
    assert made[0].amount_cents == 80_000


def test_an_estimate_above_the_threshold_on_a_tracked_thing_is_its_own_item(
    settings: Settings,
) -> None:
    with session_scope() as session:
        asset = models.Asset(
            tag="bb-0010",
            description="espresso machine",
            cost_cents=120_000,
            in_service_date="2024-01-01",
            book_life_months=60,
            tax_method=models.TaxMethod.straight_line,
            status=models.AssetStatus.disposed,
        )
        session.add(asset)
        session.flush()
        event = _event(session)
        _record(
            session,
            event.id,
            label="espresso machine",
            item_class=models.ItemClass.fixed_asset,
            cost_basis_cents=0,
            fmv_mid=70_000,
            fmv_source="model_estimate",
            book_value_cents=60_000,
            tax_basis_cents=0,
            asset_id=asset.id,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()

    assert [row.kind for row in made] == [models.ReviewKind.estimate_above_threshold]
    assert made[0].asset_id is not None


def test_a_ticket_waiting_too_long_becomes_a_task(settings: Settings) -> None:
    with session_scope() as session:
        event = _event(
            session, status=models.EventStatus.asking, created_at=_ago(300)
        )
        _record(session, event.id, label="paper cup", cost_basis_cents=12)
        session.add(
            models.Identification(
                event_id=event.id,
                method=models.IdentifyMethod.cloud,
                label="paper cup",
                confidence=0.4,
                candidates_json=json.dumps(
                    [{"label": "paper cup", "p": 0.4}, {"label": "plastic cup", "p": 0.3}]
                ),
                is_final=False,
            )
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()

    assert [row.kind for row in made] == [models.ReviewKind.unresolved_ask]
    with session_scope() as session:
        listed = review.list_items(session)
    assert [c.label for c in listed.items[0].candidates] == ["paper cup", "plastic cup"]


def test_a_ticket_waiting_a_moment_is_left_alone(settings: Settings) -> None:
    with session_scope() as session:
        event = _event(session, status=models.EventStatus.asking, created_at=_ago(5))
        _record(session, event.id)
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
    assert made == []


def test_overruling_a_confident_model_raises_an_item(settings: Settings) -> None:
    with session_scope() as session:
        event = _event(session)
        _record(session, event.id, label="bagel")
        session.add(
            models.Identification(
                event_id=event.id,
                method=models.IdentifyMethod.cloud,
                label="croissant",
                confidence=0.95,
                is_final=False,
            )
        )
        session.add(
            models.Identification(
                event_id=event.id,
                method=models.IdentifyMethod.human,
                label="bagel",
                confidence=1.0,
                is_final=True,
            )
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()

    assert [row.kind for row in made] == [models.ReviewKind.confident_overruled]
    assert "croissant" in made[0].reason


def test_approving_leaves_the_ledger_alone(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()
        item_id = made[0].id
    with session_scope() as session:
        before = len(queries.list_entries(session))
        item, reversing, difference, detail = review.approve(
            session, item_id, "nishad", "the charity confirmed it"
        )
        session.commit()
        after = len(queries.list_entries(session))

    assert item.status is models.ReviewStatus.approved
    assert item.decided_by == "nishad"
    assert item.decided_at
    assert item.note == "the charity confirmed it"
    assert reversing == []
    assert difference == 0
    assert before == after
    assert "stand as they are" in detail

    with session_scope() as session:
        corrections = list(
            session.scalars(
                select(models.Correction).where(models.Correction.field == "review")
            )
        )
    assert [row.new_value for row in corrections] == ["donation approved"]


def test_rejecting_a_donation_blocks_it_and_re_ranks(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()
        item_id = made[0].id

    with session_scope() as session:
        item, reversing, difference, detail = review.reject(session, item_id, "nishad", "")
        session.commit()

    assert item.status is models.ReviewStatus.rejected
    assert difference == 62
    assert "Donating is off the table" in detail
    assert reversing == []

    with session_scope() as session:
        rows = {
            row.option: row
            for row in session.scalars(
                select(models.OptionScore).where(models.OptionScore.event_id == event_id)
            )
        }
    assert rows[models.OptionKind.donate].allowed is False
    assert rows[models.OptionKind.donate].rank is None
    assert rows[models.OptionKind.donate].blocked_reason == review.DONATION_BLOCKED_REASON
    assert rows[models.OptionKind.trash].rank == 1


def test_rejecting_a_posting_reverses_it_and_voids_the_ticket(settings: Settings) -> None:
    with session_scope() as session:
        event = _event(session)
        _record(
            session,
            event.id,
            label="office chair",
            item_class=models.ItemClass.untracked,
            cost_basis_cents=0,
            fmv_mid=80_000,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        item_id = made[0].id
        event_id = event.id

    with session_scope() as session:
        entry = journal.inventory_toss(
            EngineItemRecord.model_validate(
                {
                    "event_id": event_id,
                    "label": "office chair",
                    "class": ItemClass.inventory,
                    "mass_g": 100.0,
                    "event_date": DAY,
                    "cost_basis_cents": 4000,
                }
            )
        )
        assert entry is not None
        queries.post_entry(session, entry, event_id=event_id)
        session.commit()

    with session_scope() as session:
        item, reversing, _moved, detail = review.reject(session, item_id, "nishad", "")
        session.commit()

    assert item.status is models.ReviewStatus.rejected
    assert len(reversing) == 1
    assert "void" in detail

    with session_scope() as session:
        entries = queries.list_entries(session, event_id=event_id)
        rows = queries.trial_balance(session)
        event_row = session.get(models.Event, event_id)
    assert len(entries) == 2
    assert event_row is not None
    assert event_row.status is models.EventStatus.void
    assert sum(row.debit_cents for row in rows) == sum(row.credit_cents for row in rows)
    assert all(row.debit_cents == row.credit_cents for row in rows)


def test_rejecting_a_disposal_puts_the_asset_back_on_the_register(
    settings: Settings,
) -> None:
    with session_scope() as session:
        asset = models.Asset(
            tag="bb-0011",
            description="mechanical keyboard",
            cost_cents=12_000,
            in_service_date="2024-03-01",
            book_life_months=36,
            tax_method=models.TaxMethod.straight_line,
            status=models.AssetStatus.disposed,
        )
        session.add(asset)
        session.flush()
        event = _event(session)
        asset.disposed_event_id = event.id
        record = _record(
            session,
            event.id,
            label="mechanical keyboard",
            item_class=models.ItemClass.fixed_asset,
            cost_basis_cents=0,
            fmv_mid=80_000,
            fmv_source="model_estimate",
            book_value_cents=3_000,
            tax_basis_cents=2_000,
            asset_id=asset.id,
        )
        pure = EngineItemRecord.model_validate(
            {
                "event_id": event.id,
                "label": record.label,
                "class": ItemClass.fixed_asset,
                "mass_g": 900.0,
                "event_date": DAY,
                "book_value_cents": 3_000,
                "tax_basis_cents": 2_000,
                "asset_id": asset.id,
            }
        )
        info = AssetInfo(
            id=asset.id,
            tag=asset.tag,
            description=asset.description,
            cost_cents=asset.cost_cents,
            book_life_months=36,
            tax_method=TaxMethod.straight_line,
            status=AssetStatus.disposed,
        )
        queries.post_entry(
            session, journal.fixed_asset_disposal(pure, info, 0), event_id=event.id
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        item_id = made[0].id
        asset_id = asset.id

    with session_scope() as session:
        _, reversing, _, detail = review.reject(session, item_id, "nishad", "")
        session.commit()

    assert len(reversing) == 1
    assert "back on the register" in detail
    with session_scope() as session:
        row = session.get(models.Asset, asset_id)
    assert row is not None
    assert row.status is models.AssetStatus.active
    assert row.disposed_event_id is None


def test_an_item_cannot_be_decided_twice(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()
        item_id = made[0].id
    with session_scope() as session:
        review.approve(session, item_id)
        session.commit()
    with session_scope() as session:
        try:
            review.reject(session, item_id)
        except review.AlreadyDecided as refused:
            assert "approved" in str(refused)
        else:  # pragma: no cover
            raise AssertionError("a decided item was decided again")


def test_a_void_ticket_raises_nothing(settings: Settings) -> None:
    with session_scope() as session:
        event = _event(session, status=models.EventStatus.void)
        _record(
            session,
            event.id,
            label="office chair",
            item_class=models.ItemClass.untracked,
            cost_basis_cents=0,
            fmv_mid=80_000,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
    assert made == []
