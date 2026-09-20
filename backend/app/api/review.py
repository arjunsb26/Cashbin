"""The review queue: list what is open, approve it, reject it, or answer the ask.

Lane P, PLAN.md 21a item 39. Every handler is thin. The queue's rules live in
`ledger/review.py`, and the answer route hands the label straight to the same
correction handler the phone and the dashboard use, so an answer given here is
the same answer given anywhere else.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import models
from app.agent import reviewer
from app.config import Settings, get_settings
from app.db import session_scope
from app.learn.corrections import CorrectionRefusedError, apply_correction
from app.ledger import review
from app.schemas import (
    CorrectionCreate,
    CorrectionResponse,
    ReviewDecision,
    ReviewDecisionResponse,
    ReviewListResponse,
    ReviewRunResponse,
    ValidatedLabel,
)

router = APIRouter(prefix="/api/review", tags=["review"])

NO_SUCH_ITEM = "That review item does not exist."


@router.get("", response_model=ReviewListResponse)
def list_review(
    item_status: models.ReviewStatus | None = Query(
        default=None, alias="status", description="Review status to filter by."
    ),
) -> ReviewListResponse:
    """Everything a person still has to settle, open items first."""
    with session_scope() as session:
        return review.list_items(session, item_status)


def _decide(item_id: int, body: ReviewDecision, approved: bool) -> ReviewDecisionResponse:
    with session_scope() as session:
        act = review.approve if approved else review.reject
        try:
            item, reversing, difference, detail = act(session, item_id, body.by, body.note)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=NO_SUCH_ITEM
            ) from None
        except review.AlreadyDecided as decided:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(decided)
            ) from decided
        read = review.to_read(session, item)
    return ReviewDecisionResponse(
        item=read,
        reversing_entry_ids=reversing,
        difference_cents=difference,
        detail=detail,
        agreed_with_agent=read.agreed_with_agent,
    )


@router.post("/run", response_model=ReviewRunResponse)
def run_agent(settings: Settings = Depends(get_settings)) -> ReviewRunResponse:
    """Have the review agent look at every open item that has no proposal yet.

    It proposes and nothing else. Every item comes back still open, with the
    agent's reading of it and the lookups it made attached.
    """
    with session_scope() as session:
        made = reviewer.run_open(session, settings)
        session.commit()
        listed = review.list_items(session, models.ReviewStatus.open)
    return ReviewRunResponse(proposed=len(made), items=listed.items)


@router.post("/{item_id}/approve", response_model=ReviewDecisionResponse)
def approve_item(item_id: int, body: ReviewDecision) -> ReviewDecisionResponse:
    """Keep what was posted. The question closes and the ledger does not move."""
    return _decide(item_id, body, approved=True)


@router.post("/{item_id}/reject", response_model=ReviewDecisionResponse)
def reject_item(item_id: int, body: ReviewDecision) -> ReviewDecisionResponse:
    """Undo what the ticket claimed. Entries are reversed, never deleted."""
    return _decide(item_id, body, approved=False)


class ReviewAnswer(ReviewDecision):
    """An answer to an unresolved ask, given from the queue."""

    label: ValidatedLabel


@router.post("/{item_id}/answer", response_model=CorrectionResponse)
async def answer_item(item_id: int, body: ReviewAnswer) -> CorrectionResponse:
    """Answer the bin's question from the queue and close the item.

    The label has already been through the same validation the ask flow uses, and
    the correction handler does the rest, so nothing about the answer depends on
    where a person happened to be standing when they gave it.
    """
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_SUCH_ITEM)
        if item.kind is not models.ReviewKind.unresolved_ask:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This item is not a question the bin asked.",
            )
        if item.status is not models.ReviewStatus.open:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"this item was already {item.status.value}",
            )
        event_id = item.event_id

    try:
        answered = await apply_correction(
            CorrectionCreate(event_id=event_id, label=body.label, by=body.by)
        )
    except CorrectionRefusedError as refused:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(refused)
        ) from refused

    with session_scope() as session:
        row = session.get(models.ReviewItem, item_id)
        if row is not None:
            review.approve(session, item_id, body.by, f"answered as {body.label}")
    return answered
