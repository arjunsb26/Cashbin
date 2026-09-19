"""Rounds, the header summary, and the improvement numbers. Lane C owns the handlers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.schemas import RoundListResponse, RoundRead, SummaryResponse

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics/rounds", response_model=RoundListResponse)
def list_rounds() -> RoundListResponse:
    not_implemented("Lane C", "The rounds list")


@router.post("/metrics/rounds/start", response_model=RoundRead)
def start_round() -> RoundRead:
    not_implemented("Lane C", "Starting a round")


@router.get("/summary", response_model=SummaryResponse)
def get_summary() -> SummaryResponse:
    not_implemented("Lane C", "The header summary")
