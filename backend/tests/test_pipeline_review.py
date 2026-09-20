"""A ticket that owes a person something says so when it finishes, not at the close.

The review queue used to be filled by the close alone, so a donation waiting for somebody
to sign it off was invisible until the end of the period. A bagel nobody opened is exactly
that case: the deduction is real and a person has to stand behind it.
"""

from __future__ import annotations

from sqlalchemy import select

from app.config import Settings
from app.db import session_scope
from app.models import IdentifyMethod, ItemClass, ReviewItem, ReviewKind
from tests.test_identify_support import setup_db
from tests.test_toss_meaning import a_pipeline, a_toss


async def test_a_donation_reaches_the_queue_as_the_ticket_finishes(
    settings: Settings,
) -> None:
    setup_db(settings)
    event_id = a_toss("bagel", ItemClass.inventory, 95.0)
    pipe = a_pipeline(settings)

    await pipe.finalise_event(event_id, "bagel", ItemClass.inventory, IdentifyMethod.stub)

    with session_scope() as session:
        rows = list(
            session.scalars(select(ReviewItem).where(ReviewItem.event_id == event_id)).all()
        )
    kinds = {row.kind for row in rows}
    assert ReviewKind.donation in kinds, "the donation never reached the queue"


async def test_a_ticket_with_nothing_to_approve_raises_nothing(settings: Settings) -> None:
    setup_db(settings)
    event_id = a_toss("pizza slice", ItemClass.inventory, 20.0)
    pipe = a_pipeline(settings)

    await pipe.finalise_event(event_id, "pizza slice", ItemClass.inventory, IdentifyMethod.stub)

    with session_scope() as session:
        rows = list(
            session.scalars(select(ReviewItem).where(ReviewItem.event_id == event_id)).all()
        )
    assert [row.kind for row in rows] != [ReviewKind.possible_unrecorded_asset]


def test_how_long_a_ticket_may_wait_is_a_setting() -> None:
    from app.ledger.review import review_after_s

    assert review_after_s(Settings(_env_file=None)) == 120.0
    assert review_after_s(Settings(_env_file=None, review_after_s=30)) == 30.0
