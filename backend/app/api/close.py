"""Period close. Lane F owns the handlers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.schemas import CloseRead, CloseRequest

router = APIRouter(prefix="/api/close", tags=["close"])


@router.post("", response_model=CloseRead)
def run_close(body: CloseRequest) -> CloseRead:
    not_implemented("Lane F", "Running a close")


@router.get("/{close_id}", response_model=CloseRead)
def get_close(close_id: int) -> CloseRead:
    not_implemented("Lane F", "The close report")
