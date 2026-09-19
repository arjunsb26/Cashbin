"""Rounds, the header summary, and the improvement numbers. Lane C owns the handlers."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.learn import metrics, rounds
from app.notify.bus import get_bus
from app.schemas import RoundListResponse, RoundRead, SummaryResponse

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics/rounds", response_model=RoundListResponse)
def list_rounds(session: Session = Depends(get_db)) -> RoundListResponse:
    """Every round, oldest first. This is what the improvement chart plots."""
    return metrics.list_rounds(session)


@router.post("/metrics/rounds/start", response_model=RoundRead)
def start_round(session: Session = Depends(get_db)) -> RoundRead:
    """Close the open round and start a fresh one."""
    fresh = rounds.start_round(session)
    session.commit()
    metrics.publish_metrics(session, get_bus())
    return metrics.round_read(fresh, session)


@router.get("/summary", response_model=SummaryResponse)
def get_summary(session: Session = Depends(get_db)) -> SummaryResponse:
    """The header totals on the Live page."""
    return metrics.summary(session)
