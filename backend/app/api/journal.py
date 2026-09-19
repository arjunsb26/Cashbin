"""Journal entries and the trial balance. Lane B owns the handler."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.ledger import queries
from app.models import JournalBasis
from app.schemas import JournalResponse

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("", response_model=JournalResponse)
def list_journal(
    basis: JournalBasis | None = Query(default=None, description="Book or tax memo."),
    session: Session = Depends(get_db),
) -> JournalResponse:
    """Every entry on this basis, with the trial balance and whether it agrees.

    With no basis given the page shows every entry, and the trial balance is the
    book one, because the tax memo is a memo and has no ledger of its own.
    """
    entries = queries.list_entries(session, basis)
    rows = queries.trial_balance(session, basis or JournalBasis.book)
    return JournalResponse(
        basis=basis,
        entries=entries,
        trial_balance=rows,
        balanced=queries.is_balanced(rows),
    )
