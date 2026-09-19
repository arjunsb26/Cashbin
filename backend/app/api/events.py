"""Event list, event detail and void. Lane A creates events, lanes B and C fill the detail."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api import not_implemented
from app.models import EventStatus
from app.schemas import EventDetail, EventListResponse, VoidResponse

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventListResponse)
def list_events(
    round_id: int | None = Query(default=None, alias="round", description="Round id to filter by."),
    event_status: EventStatus | None = Query(
        default=None, alias="status", description="Event status to filter by."
    ),
) -> EventListResponse:
    not_implemented("Lane A", "The event list")


@router.get("/{event_id}", response_model=EventDetail)
def get_event(event_id: int) -> EventDetail:
    not_implemented("Lane A", "Event detail")


@router.post("/{event_id}/void", response_model=VoidResponse)
def void_event(event_id: int) -> VoidResponse:
    not_implemented("Lane B", "Voiding a ticket")
