"""Journal entries and the trial balance. Lane B owns the handler."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api import not_implemented
from app.models import JournalBasis
from app.schemas import JournalResponse

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("", response_model=JournalResponse)
def list_journal(
    basis: JournalBasis | None = Query(default=None, description="Book or tax memo."),
) -> JournalResponse:
    not_implemented("Lane B", "The journal")
