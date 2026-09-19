"""Event list, event detail and void. Lane A creates events, lanes B and C fill the detail.

A row is written the moment the scale settles, long before anything knows what the
thing was, so every read here tolerates the later tables being empty. An event with no
identification is a real event with a mass and a picture, not a broken one.
"""

from __future__ import annotations

import importlib
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import session_scope
from app.ingest.media import media_url
from app.models import (
    Correction,
    Event,
    EventStatus,
    Identification,
    ItemRecord,
    JournalEntry,
    JournalLine,
    OptionKind,
    OptionScore,
)
from app.schemas import (
    CorrectionRead,
    EstimateRef,
    EventDetail,
    EventListResponse,
    EventSummary,
    IdentificationRead,
    ItemRecordRead,
    JournalEntryRead,
    JournalLineRead,
    OptionScoreRead,
    VisionCandidate,
    VoidResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

LIST_LIMIT = 200


def _loads(raw: str | None, fallback: Any) -> Any:
    """Read a JSON column without letting one bad row take the whole list down."""
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("a stored JSON column does not parse, using the empty value")
        return fallback


def _summary(session: Session, row: Event) -> EventSummary:
    """One event as the list and the ticket header show it."""
    record = session.get(ItemRecord, row.id)
    options = list(
        session.scalars(select(OptionScore).where(OptionScore.event_id == row.id)).all()
    )
    best = _best_option(options)
    return EventSummary(
        id=int(row.id),
        created_at=row.created_at,
        kind=row.kind,
        status=row.status,
        mass_g=row.mass_g,
        mass_err_g=row.mass_err_g,
        label=record.label if record else None,
        item_class=record.item_class if record else None,
        crop_url=media_url(row.crop),
        crop_quality=row.crop_quality,
        net_book_cents=record.book_value_cents if record else None,
        best_option=best.option if best else None,
        saved_if_followed_cents=_saved_if_followed(options, best),
        round_id=row.round_id,
    )


def _best_option(options: list[OptionScore]) -> OptionScore | None:
    """Rank 1 when the engine has ranked them, otherwise the best allowed net."""
    allowed = [o for o in options if o.allowed]
    if not allowed:
        return None
    ranked = [o for o in allowed if o.rank == 1]
    if ranked:
        return ranked[0]
    return max(allowed, key=lambda o: o.net_after_tax_cents)


def _saved_if_followed(options: list[OptionScore], best: OptionScore | None) -> int | None:
    """PLAN.md section 10 item 4: what following the best option beats binning it by."""
    if best is None:
        return None
    trash = next((o for o in options if o.option is OptionKind.trash), None)
    if trash is None:
        return None
    return best.net_after_tax_cents - trash.net_after_tax_cents


@router.get("", response_model=EventListResponse)
def list_events(
    round_id: int | None = Query(default=None, alias="round", description="Round id to filter by."),
    event_status: EventStatus | None = Query(
        default=None, alias="status", description="Event status to filter by."
    ),
) -> EventListResponse:
    """Newest first, at most 200. The Live page reads this on load and then listens."""
    with session_scope() as session:
        query = select(Event).order_by(Event.id.desc()).limit(LIST_LIMIT)
        if round_id is not None:
            query = query.where(Event.round_id == round_id)
        if event_status is not None:
            query = query.where(Event.status == event_status)
        rows = list(session.scalars(query).all())
        return EventListResponse(events=[_summary(session, row) for row in rows])


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: int) -> EventDetail:
    """Everything the ticket and the evidence drawer draw, in one read."""
    with session_scope() as session:
        row = session.get(Event, event_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such event.")
        return EventDetail(
            event=_summary(session, row),
            trace=_trace(row),
            frame_before_url=media_url(row.frame_before),
            frame_after_url=media_url(row.frame_after),
            frame_peak_url=media_url(row.frame_peak),
            identifications=_identifications(session, event_id),
            item_record=_item_record(session, event_id),
            options=_options(session, event_id),
            entries=_entries(session, event_id),
            corrections=_corrections(session, event_id),
        )


@router.post("/{event_id}/void", response_model=VoidResponse)
def void_event(event_id: int) -> VoidResponse:
    """Mark the event void and let the ledger reverse whatever it posted for it."""
    with session_scope() as session:
        row = session.get(Event, event_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such event.")
        row.status = EventStatus.void

    reversing = _reverse_in_ledger(event_id)
    return VoidResponse(
        event_id=event_id, status=EventStatus.void, reversing_entry_ids=reversing
    )


def _reverse_in_ledger(event_id: int) -> list[int]:
    """Call the ledger's reversal if it exists yet.

    Lane B owns `ledger.queries.void_event`. Importing it here rather than at module
    level means this route works before that lane lands, and starts reversing entries
    the moment it does, with no change on this side.
    """
    try:
        module = importlib.import_module("app.ledger.queries")
    except ImportError:
        log.info("no ledger reversal is available yet, event %d is marked void only", event_id)
        return []
    ledger_void = getattr(module, "void_event", None)
    if not callable(ledger_void):
        log.info("the ledger has no void_event yet, event %d is marked void only", event_id)
        return []
    try:
        result = ledger_void(event_id)
    except Exception:
        log.exception("the ledger refused to reverse event %d", event_id)
        return []
    return [int(value) for value in (result or [])]


def _trace(row: Event) -> list[list[float]]:
    raw = _loads(row.trace_json, [])
    if not isinstance(raw, list):
        return []
    return [[float(pair[0]), float(pair[1])] for pair in raw if isinstance(pair, list) and pair]


def _identifications(session: Session, event_id: int) -> list[IdentificationRead]:
    rows = session.scalars(
        select(Identification)
        .where(Identification.event_id == event_id)
        .order_by(Identification.id)
    ).all()
    out: list[IdentificationRead] = []
    for row in rows:
        candidates = [
            VisionCandidate.model_validate(item)
            for item in _loads(row.candidates_json, [])
            if isinstance(item, dict)
        ]
        out.append(
            IdentificationRead(
                id=int(row.id),
                event_id=int(row.event_id),
                method=row.method,
                label=row.label,
                item_class=row.item_class,
                confidence=row.confidence,
                candidates=candidates,
                posterior=_loads(row.posterior_json, {}),
                used_mass_prior=row.used_mass_prior,
                latency_ms=row.latency_ms,
                cost_microusd=row.cost_microusd,
                tokens_in=row.tokens_in,
                tokens_out=row.tokens_out,
                is_final=row.is_final,
                provider=row.provider,
                model=row.model,
            )
        )
    return out


def _item_record(session: Session, event_id: int) -> ItemRecordRead | None:
    row = session.get(ItemRecord, event_id)
    if row is None:
        return None
    condition = row.condition if row.condition in {"working", "broken", "unknown"} else "unknown"
    return ItemRecordRead(
        event_id=int(row.event_id),
        label=row.label,
        item_class=row.item_class,
        mass_g=row.mass_g,
        condition=condition,
        material_mix=_loads(row.material_mix_json, {}),
        regulatory_flags=_loads(row.regulatory_flags_json, []),
        book_value_cents=row.book_value_cents,
        tax_basis_cents=row.tax_basis_cents,
        asset_id=row.asset_id,
        cost_basis_cents=row.cost_basis_cents,
        fmv=EstimateRef(
            low=row.fmv_low,
            mid=row.fmv_mid,
            high=row.fmv_high,
            source=row.fmv_source,
        ),
        repair=EstimateRef(
            low=row.repair_low,
            mid=row.repair_mid,
            high=row.repair_high,
            source=row.repair_source,
        ),
        replacement_cents=row.replacement_cents,
        replacement_source=row.replacement_source,
        scrap_cents=row.scrap_cents,
        scrap_source=row.scrap_source,
    )


def _options(session: Session, event_id: int) -> list[OptionScoreRead]:
    rows = session.scalars(
        select(OptionScore).where(OptionScore.event_id == event_id).order_by(OptionScore.id)
    ).all()
    return [
        OptionScoreRead(
            id=int(row.id),
            event_id=int(row.event_id),
            option=row.option,
            allowed=row.allowed,
            blocked_reason=row.blocked_reason,
            cash_cents=row.cash_cents,
            tax_effect_cents=row.tax_effect_cents,
            net_after_tax_cents=row.net_after_tax_cents,
            kg_co2e=row.kg_co2e,
            kg_landfill=row.kg_landfill,
            needs_human_review=row.needs_human_review,
            notes=_loads(row.notes_json, []),
            rule_ids=_loads(row.rule_ids_json, []),
            rank=row.rank,
        )
        for row in rows
    ]


def _entries(session: Session, event_id: int) -> list[JournalEntryRead]:
    rows = session.scalars(
        select(JournalEntry).where(JournalEntry.event_id == event_id).order_by(JournalEntry.id)
    ).all()
    out: list[JournalEntryRead] = []
    for row in rows:
        lines = session.scalars(
            select(JournalLine).where(JournalLine.entry_id == row.id).order_by(JournalLine.id)
        ).all()
        out.append(
            JournalEntryRead(
                id=int(row.id),
                event_id=row.event_id,
                close_id=row.close_id,
                posted_at=row.posted_at,
                memo=row.memo,
                basis=row.basis,
                evidence=_loads(row.evidence_json, {}),
                lines=[
                    JournalLineRead(
                        id=int(line.id),
                        entry_id=int(line.entry_id),
                        account=line.account,
                        debit_cents=line.debit_cents,
                        credit_cents=line.credit_cents,
                    )
                    for line in lines
                ],
            )
        )
    return out


def _corrections(session: Session, event_id: int) -> list[CorrectionRead]:
    rows = session.scalars(
        select(Correction).where(Correction.event_id == event_id).order_by(Correction.id)
    ).all()
    return [
        CorrectionRead(
            id=int(row.id),
            event_id=int(row.event_id),
            field=row.field,
            old_value=row.old_value,
            new_value=row.new_value,
            by=row.by,
            created_at=row.created_at,
        )
        for row in rows
    ]
