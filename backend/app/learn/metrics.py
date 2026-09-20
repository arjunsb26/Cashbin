"""The numbers the header, the improvement chart and the learning list are drawn from.

PLAN.md section 12. Every figure here is read back out of the database. Nothing is cached,
nothing is estimated, and a period with no data reports no rate rather than a zero, because
a zero accuracy and an unknown accuracy are not the same thing in front of a judge.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Correction,
    Event,
    EventKind,
    EventStatus,
    Exemplar,
    Identification,
    IdentifyMethod,
    OptionKind,
    OptionScore,
    Round,
)
from app.notify.bus import CHANNEL_UI, Bus
from app.schemas import RoundListResponse, RoundRead, SummaryResponse, UiMetricsUpdated

# PLAN.md 21a item 23: memory no longer answers on its own, so the only identification that
# costs nothing is a QR tag. This number is smaller than it used to be and it is honest.
LOCAL_METHODS = (IdentifyMethod.qr,)
DEFAULT_LEARNED = 5


def _rate(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def local_share(session: Session, round_id: int) -> float | None:
    """The share of a round's events that never needed a call. The Token Company number."""
    total = session.execute(
        select(func.count(Event.id)).where(Event.round_id == round_id)
    ).scalar_one()
    if not total:
        return None
    local = session.execute(
        select(func.count(func.distinct(Identification.event_id)))
        .join(Event, Event.id == Identification.event_id)
        .where(
            Event.round_id == round_id,
            Identification.is_final.is_(True),
            Identification.method.in_(LOCAL_METHODS),
        )
    ).scalar_one()
    return local / total


def round_read(rnd: Round, session: Session | None = None) -> RoundRead:
    """One round with its derived rates. Pass a session to fill in the local share."""
    return RoundRead(
        id=rnd.id,
        started_at=rnd.started_at,
        ended_at=rnd.ended_at,
        n_events=rnd.n_events,
        n_correct_first_try=rnd.n_correct_first_try,
        n_asked=rnd.n_asked,
        n_corrected_after_confident=rnd.n_corrected_after_confident,
        mean_latency_ms=rnd.mean_latency_ms,
        cloud_cost_microusd=rnd.cloud_cost_microusd,
        first_try_accuracy=_rate(rnd.n_correct_first_try, rnd.n_events),
        ask_rate=_rate(rnd.n_asked, rnd.n_events),
        cost_per_event_microusd=(
            rnd.cloud_cost_microusd / rnd.n_events if rnd.n_events else None
        ),
        local_share=local_share(session, rnd.id) if session is not None else None,
    )


def list_rounds(session: Session, learned: int = DEFAULT_LEARNED) -> RoundListResponse:
    """Every round, oldest first, plus what the last few answers taught the system.

    The improvement chart plots the rounds and the Learning page reads the sentences, so
    both halves of PLAN.md section 12 arrive in one request.
    """
    rounds = session.execute(select(Round).order_by(Round.id)).scalars().all()
    return RoundListResponse(
        rounds=[round_read(rnd, session) for rnd in rounds],
        learned=what_learned(session, learned),
    )


def summary(session: Session) -> SummaryResponse:
    """The four header numbers. Saved and diverted come from the engine's option rows."""
    # Tosses, which is the word the header uses. A bag going out is a row on the chart,
    # not something anyone threw away, so it is not counted here.
    events = session.execute(
        select(func.count(Event.id)).where(
            Event.status != EventStatus.void, Event.kind == EventKind.toss
        )
    ).scalar_one()

    saved_cents = 0
    kg_diverted = 0.0
    scores = session.execute(select(OptionScore)).scalars().all()
    by_event: dict[int, list[OptionScore]] = {}
    for score in scores:
        by_event.setdefault(score.event_id, []).append(score)
    for rows in by_event.values():
        trash = next((r for r in rows if r.option is OptionKind.trash), None)
        ranked = sorted(
            (r for r in rows if r.allowed and r.rank is not None), key=lambda r: r.rank or 0
        )
        best = ranked[0] if ranked else None
        if best is None or trash is None:
            continue
        saved_cents += max(best.net_after_tax_cents - trash.net_after_tax_cents, 0)
        kg_diverted += max(trash.kg_landfill - best.kg_landfill, 0.0)

    totals = session.execute(
        select(
            func.coalesce(func.sum(Round.n_correct_first_try), 0),
            func.coalesce(func.sum(Round.n_events), 0),
        )
    ).one()
    return SummaryResponse(
        saved_if_followed_cents=saved_cents,
        kg_diverted=round(kg_diverted, 3),
        events=events,
        first_try_accuracy=_rate(int(totals[0]), int(totals[1])),
    )


def what_learned(session: Session, limit: int = DEFAULT_LEARNED) -> list[str]:
    """The most recent corrections in plain words, for the learning list on the dashboard."""
    rows = (
        session.execute(
            select(Correction)
            .where(Correction.field == "label")
            .order_by(Correction.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    sentences: list[str] = []
    for row in rows:
        label = row.new_value or ""
        if not label:
            continue
        examples = session.execute(
            select(func.count(Exemplar.id)).where(Exemplar.label == label)
        ).scalar_one()
        seen = f"now recognised from {examples} example{'' if examples == 1 else 's'}"
        old = (row.old_value or "").strip()
        if old and old != label:
            sentences.append(f"{old} vs {label}: {seen}")
        else:
            sentences.append(f"{label}: {seen}")
    return sentences


def publish_metrics(session: Session, bus: Bus) -> None:
    """Push the header and the open round to the dashboard after every event."""
    from app.learn.rounds import open_round

    rnd = open_round(session)
    bus.publish(
        UiMetricsUpdated(
            summary=summary(session),
            round=round_read(rnd, session) if rnd is not None else None,
        ),
        CHANNEL_UI,
    )
