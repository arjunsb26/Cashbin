"""The scenario every close test is built on, plus the checks that it is sound.

One period: five tosses, one bag change, a tare, four inventory write-offs and
one fixed asset disposal with its tax memo. The weight traces are consistent
with the tickets on purpose, so mass conservation passes here and every failure
test is one deliberate change away.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.engine.records import AssetInfo, AssetStatus, ItemClass, TaxMethod
from app.engine.records import ItemRecord as EngineItemRecord
from app.engine.tax import TaxEffect
from app.ledger import journal, queries

DAY = "2026-09-19"
PERIOD_START = "2026-09-19"
PERIOD_END = "2026-09-19"


def at(second: int) -> str:
    return f"{DAY}T12:{second // 60:02d}:{second % 60:02d}+00:00"


def trace(points: list[tuple[float, float]]) -> str:
    return json.dumps([[t, g] for t, g in points])


@dataclass
class Scenario:
    """Ids the tests reach for by name rather than by guessing."""

    toss_ids: list[int] = field(default_factory=list)
    bag_change_id: int = 0
    asset_id: int = 0
    asset_event_id: int = 0
    food_event_id: int = 0


# The timeline. Grams are cumulative bin weight, so the traces and the tickets agree.
_TOSSES: list[dict[str, Any]] = [
    {
        "label": "pizza slice",
        "class": models.ItemClass.inventory,
        "mass_g": 107.0,
        "mass_err_g": 1.0,
        "cost_basis_cents": 100,
        "trace": [(0.0, 0.0), (0.5, 40.0), (1.0, 107.0)],
        "created_at": at(0),
        "material": {"food_waste": 1.0},
        "flags": ["food"],
    },
    {
        "label": "bagel",
        "class": models.ItemClass.inventory,
        "mass_g": 95.0,
        "mass_err_g": 1.2,
        "cost_basis_cents": 33,
        "trace": [(2.0, 107.0), (3.0, 202.0)],
        "created_at": at(30),
        "material": {"food_waste": 1.0},
        "flags": ["food"],
    },
    {
        "label": "cardboard box",
        "class": models.ItemClass.inventory,
        "mass_g": 250.0,
        "mass_err_g": 2.0,
        "cost_basis_cents": 40,
        "trace": [(4.0, 202.0), (5.0, 452.0)],
        "created_at": at(60),
        "material": {"corrugated_containers": 1.0},
        "flags": [],
    },
    {
        "label": "mechanical keyboard",
        "class": models.ItemClass.fixed_asset,
        "mass_g": 900.0,
        "mass_err_g": 3.0,
        "cost_basis_cents": 0,
        "book_value_cents": 3000,
        "tax_basis_cents": 2000,
        "trace": [(8.0, 0.0), (9.0, 900.0)],
        "created_at": at(120),
        "material": {"mixed_plastics": 0.6, "steel_cans": 0.4},
        "flags": ["electronics"],
    },
    {
        "label": "paper cup",
        "class": models.ItemClass.inventory,
        "mass_g": 45.0,
        "mass_err_g": 0.8,
        "cost_basis_cents": 12,
        "trace": [(10.0, 900.0), (11.0, 945.0)],
        "created_at": at(150),
        "material": {"mixed_paper": 1.0},
        "flags": [],
    },
]

_BAG_CHANGE = {
    "mass_g": -452.0,
    "mass_err_g": 2.5,
    "trace": [(6.0, 452.0), (7.0, 0.0)],
    "created_at": at(90),
}

# Option scores per label: (option, allowed, net_after_tax_cents, kg_co2e, kg_landfill, rank)
_OPTIONS: dict[str, list[tuple[models.OptionKind, bool, int, float | None, float, int | None]]] = {
    "pizza slice": [
        (models.OptionKind.trash, True, -3, 0.5, 0.107, 2),
        (models.OptionKind.donate, True, 147, 0.02, 0.0, 1),
    ],
    "bagel": [
        (models.OptionKind.trash, True, -2, 0.44, 0.095, 2),
        (models.OptionKind.donate, True, 60, 0.01, 0.0, 1),
    ],
    "cardboard box": [
        (models.OptionKind.trash, True, -5, 1.1, 0.25, 2),
        (models.OptionKind.recycle, True, 6, -0.8, 0.0, 1),
    ],
    "mechanical keyboard": [
        (models.OptionKind.trash, False, -630, 2.4, 0.9, None),
        (models.OptionKind.recycle, True, -600, 0.9, 0.0, 2),
        (models.OptionKind.resell, True, 1200, -3.0, 0.0, 1),
    ],
    "paper cup": [
        (models.OptionKind.trash, True, -1, 0.2, 0.045, 1),
        (models.OptionKind.recycle, True, -4, 0.05, 0.0, 2),
    ],
}


def _add_event(
    session: Session,
    kind: models.EventKind,
    spec: dict[str, Any],
    status: models.EventStatus = models.EventStatus.posted,
) -> models.Event:
    row = models.Event(
        created_at=spec["created_at"],
        kind=kind,
        mass_g=spec["mass_g"],
        mass_err_g=spec["mass_err_g"],
        trace_json=trace(spec["trace"]),
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def _add_item_record(session: Session, event_id: int, spec: dict[str, Any]) -> models.ItemRecord:
    row = models.ItemRecord(
        event_id=event_id,
        label=spec["label"],
        item_class=spec["class"],
        mass_g=spec["mass_g"],
        condition="unknown",
        material_mix_json=json.dumps(spec["material"]),
        regulatory_flags_json=json.dumps(spec["flags"]),
        book_value_cents=spec.get("book_value_cents", 0),
        tax_basis_cents=spec.get("tax_basis_cents", 0),
        cost_basis_cents=spec.get("cost_basis_cents", 0),
        asset_id=spec.get("asset_id"),
        fmv_mid=spec.get("fmv_mid"),
        fmv_source=spec.get("fmv_source"),
    )
    session.add(row)
    session.flush()
    return row


def _add_options(session: Session, event_id: int, label: str) -> None:
    for option, allowed, net, co2e, landfill, rank in _OPTIONS.get(label, []):
        session.add(
            models.OptionScore(
                event_id=event_id,
                option=option,
                allowed=allowed,
                blocked_reason=None if allowed else "Electronics may not go to landfill.",
                cash_cents=net,
                tax_effect_cents=0,
                net_after_tax_cents=net,
                kg_co2e=co2e,
                kg_landfill=landfill,
                notes_json=json.dumps([]),
                rule_ids_json=json.dumps([]),
                rank=rank,
            )
        )
    session.flush()


def _add_identification(
    session: Session, event_id: int, method: models.IdentifyMethod, label: str
) -> None:
    session.add(
        models.Identification(
            event_id=event_id,
            method=method,
            label=label,
            item_class=models.ItemClass.inventory,
            confidence=0.93,
            is_final=True,
            provider="stub",
            model="",
        )
    )
    session.flush()


def _engine_record(row: models.ItemRecord, spec: dict[str, Any]) -> EngineItemRecord:
    from datetime import date

    return EngineItemRecord.model_validate(
        {
            "event_id": row.event_id,
            "label": row.label,
            "class": ItemClass(row.item_class.value),
            "mass_g": row.mass_g,
            "event_date": date.fromisoformat(DAY),
            "material_mix": spec["material"],
            "regulatory_flags": spec["flags"],
            "book_value_cents": row.book_value_cents,
            "tax_basis_cents": row.tax_basis_cents,
            "cost_basis_cents": row.cost_basis_cents,
            "asset_id": row.asset_id,
        }
    )


def build_clean_scenario(session: Session) -> Scenario:
    """One tidy period. Every check passes on what this builds."""
    scenario = Scenario()

    session.add(
        models.Setting(
            key="last_tare",
            value_json=json.dumps({"at": at(0), "weight_g": 0.0}),
        )
    )

    asset = models.Asset(
        tag="bb-0002",
        description="mechanical keyboard",
        category="computer equipment",
        cost_cents=12000,
        in_service_date="2024-03-01",
        book_life_months=36,
        salvage_cents=0,
        tax_method=models.TaxMethod.straight_line,
        status=models.AssetStatus.disposed,
        insured=False,
        location="office",
    )
    session.add(asset)
    session.flush()
    scenario.asset_id = asset.id

    order: list[int | None] = [0, 1, 2, None, 3, 4]
    for slot in order:
        if slot is None:
            bag = _add_event(session, models.EventKind.bag_change, _BAG_CHANGE)
            scenario.bag_change_id = bag.id
            continue
        spec = dict(_TOSSES[slot])
        if spec["class"] is models.ItemClass.fixed_asset:
            spec["asset_id"] = asset.id
        event = _add_event(session, models.EventKind.toss, spec)
        scenario.toss_ids.append(event.id)
        record = _add_item_record(session, event.id, spec)
        _add_options(session, event.id, spec["label"])
        _add_identification(session, event.id, models.IdentifyMethod.stub, spec["label"])

        pure = _engine_record(record, spec)
        if spec["class"] is models.ItemClass.inventory:
            scenario.food_event_id = scenario.food_event_id or event.id
            entry = journal.inventory_toss(pure)
            if entry is not None:
                queries.post_entry(session, entry, event_id=event.id)
        else:
            scenario.asset_event_id = event.id
            asset.disposed_event_id = event.id
            info = AssetInfo(
                id=asset.id,
                tag=asset.tag,
                description=asset.description,
                cost_cents=asset.cost_cents,
                book_life_months=asset.book_life_months,
                tax_method=TaxMethod.straight_line,
                status=AssetStatus.disposed,
                location=asset.location,
            )
            queries.post_entry(
                session, journal.fixed_asset_disposal(pure, info, 0), event_id=event.id
            )
            effect = TaxEffect(
                cash_cents=0,
                tax_effect_cents=420,
                deduction_cents=2000,
                gain_cents=0,
                rule_ids=("ABANDONMENT_ORDINARY_LOSS",),
            )
            queries.post_entry(session, journal.tax_memo(pure, info, effect), event_id=event.id)

    session.commit()
    return scenario


def delete_event(session: Session, event_id: int) -> None:
    """Take one ticket out of the books entirely, the way a lost event looks."""
    for score in session.scalars(
        select(models.OptionScore).where(models.OptionScore.event_id == event_id)
    ):
        session.delete(score)
    for ident in session.scalars(
        select(models.Identification).where(models.Identification.event_id == event_id)
    ):
        session.delete(ident)
    record = session.get(models.ItemRecord, event_id)
    if record is not None:
        session.delete(record)
    entries = list(
        session.scalars(
            select(models.JournalEntry).where(models.JournalEntry.event_id == event_id)
        )
    )
    for entry in entries:
        for line in session.scalars(
            select(models.JournalLine).where(models.JournalLine.entry_id == entry.id)
        ):
            session.delete(line)
    session.flush()
    for entry in entries:
        session.delete(entry)
    session.flush()
    for asset in session.scalars(
        select(models.Asset).where(models.Asset.disposed_event_id == event_id)
    ):
        asset.disposed_event_id = None
    session.flush()
    event = session.get(models.Event, event_id)
    if event is not None:
        session.delete(event)
    session.commit()


def add_ghost_asset(session: Session, event_id: int) -> models.Asset:
    """An asset the bin threw away that the register still shows as in use."""
    asset = models.Asset(
        tag="bb-0007",
        description="label printer",
        cost_cents=8000,
        in_service_date="2023-06-01",
        book_life_months=36,
        tax_method=models.TaxMethod.straight_line,
        status=models.AssetStatus.active,
        location="office",
    )
    session.add(asset)
    session.flush()
    record = session.get(models.ItemRecord, event_id)
    assert record is not None
    record.asset_id = asset.id
    session.commit()
    return asset


def test_clean_scenario_builds(settings: Settings) -> None:
    from app.db import session_scope

    with session_scope() as session:
        scenario = build_clean_scenario(session)
    assert len(scenario.toss_ids) == 5
    assert scenario.bag_change_id > 0
    assert scenario.asset_event_id in scenario.toss_ids
