"""Rounds: the batches the improvement chart is drawn from.

PLAN.md section 12. A round is a batch of events. It closes on demand from the dashboard or
automatically every `round_size` events. The counters are written as events happen, because
the chart has to be real data from the database, never a number computed for a slide.

First-try correct is counted when the system answered confidently without asking. A person
who later overturns that confident answer moves the event out of the first-try column and
into `n_corrected_after_confident`, which is the number that should stay near zero.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Event, Round, utc_now_iso


def open_round(session: Session) -> Round | None:
    """The round still taking events, if there is one."""
    return (
        session.execute(
            select(Round).where(Round.ended_at.is_(None)).order_by(Round.id.desc())
        )
        .scalars()
        .first()
    )


def start_round(session: Session) -> Round:
    """Close whatever is open and open a fresh one. The dashboard button lands here."""
    current = open_round(session)
    if current is not None:
        current.ended_at = utc_now_iso()
    fresh = Round()
    session.add(fresh)
    session.flush()
    return fresh


def current_round(session: Session, settings: Settings) -> Round:
    """The round this event belongs to, rolling over every `round_size` events."""
    current = open_round(session)
    if current is None:
        return start_round(session)
    if current.n_events >= settings.round_size:
        return start_round(session)
    return current


def record_event(
    session: Session,
    settings: Settings,
    *,
    event: Event,
    asked: bool,
    confident: bool,
    latency_ms: int | None = None,
    cost_microusd: int | None = None,
) -> Round:
    """Fold one finished identification into its round's counters."""
    rnd = current_round(session, settings)
    if event.round_id is None:
        event.round_id = rnd.id
    elif event.round_id != rnd.id:
        existing = session.get(Round, event.round_id)
        if existing is not None:
            rnd = existing

    rnd.n_events += 1
    if asked:
        rnd.n_asked += 1
    elif confident:
        rnd.n_correct_first_try += 1
    if latency_ms is not None:
        previous = rnd.mean_latency_ms or 0.0
        rnd.mean_latency_ms = previous + (latency_ms - previous) / rnd.n_events
    if cost_microusd:
        rnd.cloud_cost_microusd += cost_microusd
    session.flush()
    return rnd


def count_override(session: Session, event: Event) -> Round | None:
    """A person overturned a confident answer. Move it out of the first-try column."""
    if event.round_id is None:
        return None
    rnd = session.get(Round, event.round_id)
    if rnd is None:
        return None
    rnd.n_corrected_after_confident += 1
    if rnd.n_correct_first_try > 0:
        rnd.n_correct_first_try -= 1
    session.flush()
    return rnd
