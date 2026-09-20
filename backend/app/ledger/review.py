"""The review queue: the questions a person has to settle before the period closes.

PLAN.md 21a item 39. A ticket gets a review item when the books took a position
that a person, not a model, is supposed to own:

1. `donation`, when the best option for the ticket is one the tax rules say a
   person has to sign off. The donation rules are the only ones carrying
   `needs_human_review`, so this is where they land.
2. `estimate_above_threshold`, when a figure that came from a model estimate is
   larger than the capitalization threshold. Big money resting on a guess.
3. `possible_unrecorded_asset`, when something untracked and valuable went in the
   bin. This is `journal.untracked_flag`, raised once, here as a task.
4. `unresolved_ask`, when a ticket has been waiting on a person longer than
   `review_after_s`.
5. `confident_overruled`, when a person had to correct an identification the
   model was confident about.

Cases 2 and 3 test the same figure against the same threshold, so a ticket that
raises the unrecorded asset flag gets that item and not the estimate one. One
question per ticket per kind, enforced by a unique constraint on the table.

Approving keeps what was posted. Rejecting undoes it: for a donation the option
is blocked and the ticket is re-ranked without it, for anything else the entries
are reversed through `queries.void_event` and the ticket leaves the books. Every
decision writes a `correction` row with `field=review`, so the audit trail shows
who decided what and when.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.engine.records import ItemClass as EngineItemClass
from app.engine.tax import money
from app.ledger import queries
from app.ledger.journal import looks_unrecorded
from app.schemas import AskCandidate, ReviewItemRead, ReviewListResponse

# No setting by this name exists yet, so the default is read through getattr. When one is
# added to Settings it takes over with no change here.
REVIEW_AFTER_S_DEFAULT = 120.0
MODEL_ESTIMATE_SOURCE = "model_estimate"

DONATION_BLOCKED_REASON = "A person rejected this deduction on review."
REJECT_CORRECTION_FIELD = "review"


def review_after_s(settings: Any) -> float:
    """How long a ticket may wait on a person before it becomes a review task."""
    value = getattr(settings, "review_after_s", REVIEW_AFTER_S_DEFAULT)
    try:
        return float(value)
    except (TypeError, ValueError):
        return REVIEW_AFTER_S_DEFAULT


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _event_time(row: models.Event) -> datetime:
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _best_option(scores: list[models.OptionScore]) -> models.OptionScore | None:
    """Rank 1 when the engine ranked them, otherwise the best allowed net."""
    allowed = [row for row in scores if row.allowed]
    if not allowed:
        return None
    ranked = [row for row in allowed if row.rank == 1]
    if ranked:
        return ranked[0]
    return max(allowed, key=lambda row: row.net_after_tax_cents)


def _scores(session: Session, event_id: int) -> list[models.OptionScore]:
    return list(
        session.scalars(
            select(models.OptionScore)
            .where(models.OptionScore.event_id == event_id)
            .order_by(models.OptionScore.id)
        )
    )


def _existing(session: Session, event_id: int) -> dict[models.ReviewKind, models.ReviewItem]:
    rows = session.scalars(
        select(models.ReviewItem).where(models.ReviewItem.event_id == event_id)
    )
    return {row.kind: row for row in rows}


def _saved_if_followed(scores: list[models.OptionScore]) -> int:
    """What following the best option beats binning it by, never below zero."""
    best = _best_option(scores)
    trash = next((row for row in scores if row.option is models.OptionKind.trash), None)
    if best is None or trash is None:
        return 0
    return max(best.net_after_tax_cents - trash.net_after_tax_cents, 0)


# What to raise ------------------------------------------------------------


def _donation_item(
    event: models.Event, record: models.ItemRecord | None, scores: list[models.OptionScore]
) -> dict[str, Any] | None:
    best = _best_option(scores)
    if best is None or not best.needs_human_review:
        return None
    label = record.label if record is not None else "this item"
    amount = _saved_if_followed(scores)
    if best.option is models.OptionKind.donate:
        kind = models.ReviewKind.donation
        reason = (
            f"Donating the {label} is the best option by {money(amount)}, and the deduction "
            "needs a person to sign it off."
        )
    else:
        kind = models.ReviewKind.estimate_above_threshold
        reason = (
            f"Selling the {label} is the best option by {money(amount)}, and nothing on the "
            "books records what it cost, so the whole price is treated as gain."
        )
    return {
        "kind": kind,
        "amount_cents": amount,
        "reason": reason,
        "asset_id": record.asset_id if record is not None else None,
    }


def _unrecorded_item(
    record: models.ItemRecord | None, threshold_cents: int
) -> dict[str, Any] | None:
    if record is None or record.fmv_mid is None:
        return None
    if not looks_unrecorded(
        EngineItemClass(record.item_class.value), record.fmv_mid, threshold_cents
    ):
        return None
    return {
        "kind": models.ReviewKind.possible_unrecorded_asset,
        "amount_cents": record.fmv_mid,
        "reason": (
            f"The {record.label} is worth about {money(record.fmv_mid)}, above the "
            f"{money(threshold_cents)} limit for the register, and it was not on it."
        ),
        "asset_id": None,
    }


def _estimate_item(
    record: models.ItemRecord | None, threshold_cents: int
) -> dict[str, Any] | None:
    """A model estimate carrying more money than the register threshold allows."""
    if record is None or record.fmv_mid is None:
        return None
    if record.fmv_source != MODEL_ESTIMATE_SOURCE:
        return None
    if record.fmv_mid <= threshold_cents:
        return None
    return {
        "kind": models.ReviewKind.estimate_above_threshold,
        "amount_cents": record.fmv_mid,
        "reason": (
            f"The {money(record.fmv_mid)} on the {record.label} is an estimate, not a price "
            f"anyone paid, and it is above the {money(threshold_cents)} limit."
        ),
        "asset_id": record.asset_id,
    }


def _ask_item(
    event: models.Event, record: models.ItemRecord | None, wait_s: float, now: datetime
) -> dict[str, Any] | None:
    if event.status is not models.EventStatus.asking:
        return None
    waited = (now - _event_time(event)).total_seconds()
    if waited < wait_s:
        return None
    label = record.label if record is not None else "a ticket"
    return {
        "kind": models.ReviewKind.unresolved_ask,
        "amount_cents": 0,
        "reason": (
            f"The bin asked about {label} and has been waiting "
            f"{int(waited)} seconds. Nothing is posted until it is answered."
        ),
        "asset_id": None,
    }


def _overruled_item(
    session: Session, event: models.Event, confident_p: float
) -> dict[str, Any] | None:
    """A person had to correct a label the model was sure about."""
    rows = list(
        session.scalars(
            select(models.Identification)
            .where(models.Identification.event_id == event.id)
            .order_by(models.Identification.id)
        )
    )
    final = next((row for row in rows if row.is_final), None)
    if final is None or final.method is not models.IdentifyMethod.human:
        return None
    confident = [
        row
        for row in rows
        if row.method is not models.IdentifyMethod.human
        and (row.confidence or 0.0) >= confident_p
        and row.label
        and row.label != final.label
    ]
    if not confident:
        return None
    was = confident[-1]
    return {
        "kind": models.ReviewKind.confident_overruled,
        "amount_cents": 0,
        "reason": (
            f"The model called this a {was.label} at {(was.confidence or 0.0) * 100:.0f} "
            f"percent and a person made it a {final.label}. Check what was posted."
        ),
        "asset_id": None,
    }


def create_for_event(
    session: Session, event_id: int, settings: Any | None = None
) -> list[models.ReviewItem]:
    """Raise whatever this ticket owes a person. Safe to call again on the same ticket.

    The pipeline calls this when a ticket finishes, and the close calls it over the
    whole period as a catch-up, so a ticket that changed after it was posted still
    reaches the queue.
    """
    from app.config import get_settings

    active = settings or get_settings()
    event = session.get(models.Event, event_id)
    if event is None or event.kind is not models.EventKind.toss:
        return []
    if event.status is models.EventStatus.void:
        return []

    record = session.get(models.ItemRecord, event_id)
    scores = _scores(session, event_id)
    threshold = int(getattr(active, "capitalization_threshold_cents", 50_000))
    confident_p = float(getattr(active, "confident_p", 0.8))
    now = datetime.now(UTC)

    candidates: list[dict[str, Any]] = []
    for found in (
        _donation_item(event, record, scores),
        _unrecorded_item(record, threshold),
        _ask_item(event, record, review_after_s(active), now),
        _overruled_item(session, event, confident_p),
    ):
        if found is not None:
            candidates.append(found)

    # Cases 2 and 3 look at the same figure. The unrecorded asset is the sharper
    # question, so it wins and the estimate item is not raised beside it.
    kinds = {found["kind"] for found in candidates}
    if models.ReviewKind.possible_unrecorded_asset not in kinds:
        estimate = _estimate_item(record, threshold)
        if estimate is not None and models.ReviewKind.estimate_above_threshold not in kinds:
            candidates.append(estimate)

    already = _existing(session, event_id)
    made: list[models.ReviewItem] = []
    for found in candidates:
        kind = found["kind"]
        if kind in already:
            continue
        row = models.ReviewItem(
            kind=kind,
            event_id=event_id,
            asset_id=found["asset_id"],
            amount_cents=int(found["amount_cents"]),
            reason=str(found["reason"])[:240],
            status=models.ReviewStatus.open,
        )
        session.add(row)
        already[kind] = row
        made.append(row)
    session.flush()
    return made


def create_for_period(
    session: Session, event_ids: list[int], settings: Any | None = None
) -> list[models.ReviewItem]:
    """The close's catch-up pass over a whole period."""
    made: list[models.ReviewItem] = []
    for event_id in event_ids:
        made.extend(create_for_event(session, event_id, settings))
    return made


# Reading ------------------------------------------------------------------


def _label(session: Session, event_id: int) -> str | None:
    record = session.get(models.ItemRecord, event_id)
    return record.label if record is not None else None


def _tag(session: Session, asset_id: int | None) -> str | None:
    if asset_id is None:
        return None
    asset = session.get(models.Asset, asset_id)
    return asset.tag if asset is not None else None


def ask_candidates(session: Session, event_id: int) -> list[AskCandidate]:
    """What the bin was asking about, so the queue can answer it.

    A candidate whose label no longer validates is dropped rather than patched. The
    labels came from a model, so they go through the same wall as any outside text.
    """
    from app.identify.pipeline import read_candidates

    row = session.scalars(
        select(models.Identification)
        .where(models.Identification.event_id == event_id)
        .order_by(models.Identification.id.desc())
    ).first()
    if row is None:
        return []
    out: list[AskCandidate] = []
    for item in read_candidates(_loads(row.candidates_json, [])):
        try:
            out.append(AskCandidate.model_validate(item))
        except ValueError:
            continue
    return out[:4]


def to_read(session: Session, row: models.ReviewItem) -> ReviewItemRead:
    """One row as the Review tab reads it, with the ticket's label filled in."""
    candidates = (
        ask_candidates(session, row.event_id)
        if row.kind is models.ReviewKind.unresolved_ask
        else []
    )
    from app.agent.reviewer import stored

    proposal = stored(row)
    return ReviewItemRead(
        candidates=candidates,
        proposal=proposal,
        agreed_with_agent=row.agreed_with_agent,
        id=row.id,
        kind=row.kind,
        status=row.status,
        event_id=row.event_id,
        label=_label(session, row.event_id),
        asset_id=row.asset_id,
        asset_tag=_tag(session, row.asset_id),
        amount_cents=row.amount_cents,
        reason=row.reason,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        note=row.note,
        created_at=row.created_at,
    )


def list_items(
    session: Session, status: models.ReviewStatus | None = None
) -> ReviewListResponse:
    """Every review item, open ones first, newest first inside each group."""
    query = select(models.ReviewItem).order_by(models.ReviewItem.id)
    if status is not None:
        query = query.where(models.ReviewItem.status == status)
    rows = list(session.scalars(query))
    rows.sort(key=lambda row: (row.status is not models.ReviewStatus.open, -row.id))

    open_count = len(
        list(
            session.scalars(
                select(models.ReviewItem).where(
                    models.ReviewItem.status == models.ReviewStatus.open
                )
            )
        )
    )
    return ReviewListResponse(
        items=[to_read(session, row) for row in rows],
        open_count=open_count,
    )


def open_count(session: Session) -> int:
    return len(
        list(
            session.scalars(
                select(models.ReviewItem).where(
                    models.ReviewItem.status == models.ReviewStatus.open
                )
            )
        )
    )


# Deciding -----------------------------------------------------------------


class AlreadyDecided(ValueError):  # noqa: N818
    """Raised when someone decides an item a second time."""


def _record_correction(
    session: Session, item: models.ReviewItem, new_value: str, by: str
) -> None:
    session.add(
        models.Correction(
            event_id=item.event_id,
            field=REJECT_CORRECTION_FIELD,
            old_value=f"{item.kind.value} open",
            new_value=new_value[:200],
            by=by[:40],
        )
    )
    session.flush()


# What a person clicking approve or reject means the agent got right.
_AGREES: dict[models.ReviewStatus, str] = {
    models.ReviewStatus.approved: "approve",
    models.ReviewStatus.rejected: "reject",
}


def _mark(
    item: models.ReviewItem, status: models.ReviewStatus, by: str, note: str
) -> None:
    item.status = status
    item.decided_by = by[:40] or "person"
    item.decided_at = models.utc_now_iso()
    item.note = note[:240] or None
    item.agreed_with_agent = _agreement(item, status)


def _agreement(item: models.ReviewItem, status: models.ReviewStatus) -> bool | None:
    """Did the person go the way the agent proposed?

    Nothing is recorded when the agent had no proposal, or when it proposed
    ask_person, because asking a person and then the person deciding is not a
    disagreement. Only a real call against a real call counts.
    """
    from app.agent.reviewer import DECISION_ASK, stored

    proposal = stored(item)
    if proposal is None or proposal.decision == DECISION_ASK:
        return None
    return proposal.decision == _AGREES.get(status)


def approve(
    session: Session, item_id: int, by: str = "person", note: str = ""
) -> tuple[models.ReviewItem, list[int], int, str]:
    """Keep what was posted and close the question. Nothing in the ledger moves."""
    item = session.get(models.ReviewItem, item_id)
    if item is None:
        raise KeyError(item_id)
    if item.status is not models.ReviewStatus.open:
        raise AlreadyDecided(f"this item was already {item.status.value}")

    _mark(item, models.ReviewStatus.approved, by, note)
    _record_correction(session, item, f"{item.kind.value} approved", by)
    session.flush()
    return item, [], 0, "The entries already posted for this ticket stand as they are."


def _reject_donation(
    session: Session, item: models.ReviewItem
) -> tuple[list[int], int, str]:
    """Block the donate option, re-rank what is left, and reverse any entry it drove.

    The bin never posted the donation: the item was thrown away and the deduction was
    an option nobody had taken yet. What rejecting changes is the ranking, so the
    close stops claiming money the business is not going to get. Any tax memo entry
    that cited a donation rule is reversed, because that one was posted.
    """
    scores = _scores(session, item.event_id)
    before = _saved_if_followed(scores)

    for row in scores:
        if row.option is models.OptionKind.donate:
            row.allowed = False
            row.blocked_reason = DONATION_BLOCKED_REASON
            row.rank = None
            rule_ids = _loads(row.rule_ids_json, [])
            if isinstance(rule_ids, list):
                row.rule_ids_json = json.dumps(rule_ids)
    _rerank(session, scores)
    session.flush()

    after = _saved_if_followed(_scores(session, item.event_id))
    reversed_ids = _reverse_donation_entries(session, item.event_id)
    difference = before - after
    detail = (
        f"Donating is off the table for this ticket. What following the best option "
        f"would have been worth falls from {money(before)} to {money(after)}."
    )
    return reversed_ids, difference, detail


def _rerank(session: Session, scores: list[models.OptionScore]) -> None:
    """Re-rank the allowed options by net after tax, greenest first on a tie.

    The engine ranks with a tie break in `options.py`. This is the same order on the
    stored rows: money first, carbon inside a tie, and an unknown carbon figure never
    wins one.
    """
    from app.engine.options import _rank
    from app.ledger.close import to_engine_scores

    allowed = [row for row in scores if row.allowed]
    engine_scores = to_engine_scores(allowed)
    _rank(engine_scores, _engine_settings())
    by_id = {score.id: score.rank for score in engine_scores}
    for row in scores:
        row.rank = by_id.get(row.id) if row.allowed else None


def _engine_settings() -> Any:
    from app.config import get_settings
    from app.engine.records import EngineSettings

    return EngineSettings.from_settings(get_settings())


_DONATION_RULES = frozenset({"DONATE_FOOD", "DONATE_EQUIP"})


def _reverse_donation_entries(session: Session, event_id: int) -> list[int]:
    """Reverse any entry whose evidence cites a donation rule. Usually there are none."""
    from app.ledger.journal import reversal

    rows = list(
        session.scalars(
            select(models.JournalEntry)
            .where(models.JournalEntry.event_id == event_id)
            .order_by(models.JournalEntry.id)
        )
    )
    prefix = "Reversal of: "
    already = {row.memo.removeprefix(prefix) for row in rows if row.memo.startswith(prefix)}
    out: list[int] = []
    for row in rows:
        if row.memo.startswith(prefix) or row.memo in already:
            continue
        evidence = _loads(row.evidence_json, {})
        rule_ids = evidence.get("rule_ids") if isinstance(evidence, dict) else None
        if not isinstance(rule_ids, list) or not _DONATION_RULES.intersection(rule_ids):
            continue
        lines = list(
            session.scalars(
                select(models.JournalLine)
                .where(models.JournalLine.entry_id == row.id)
                .order_by(models.JournalLine.id)
            )
        )
        pure = queries._to_pure(row, lines)
        posted = queries.post_entry(
            session, reversal(pure), event_id=event_id, close_id=row.close_id
        )
        out.append(posted.id)
    return out


def _reject_posting(session: Session, item: models.ReviewItem) -> tuple[list[int], int, str]:
    """Take the ticket out of the books: reverse every entry, void it, put the asset back."""
    reversed_ids = queries.void_event(session, item.event_id)
    event = session.get(models.Event, item.event_id)
    if event is not None:
        event.status = models.EventStatus.void

    moved = 0
    for asset in session.scalars(
        select(models.Asset).where(models.Asset.disposed_event_id == item.event_id)
    ):
        asset.status = models.AssetStatus.active
        asset.disposed_event_id = None
        moved += asset.cost_cents
    session.flush()

    detail = (
        f"{len(reversed_ids)} entries were reversed and the ticket is void."
        if reversed_ids
        else "There was nothing posted for this ticket, so it is void with no reversal."
    )
    if moved:
        detail += " The asset is back on the register."
    return reversed_ids, item.amount_cents, detail


def reject(
    session: Session, item_id: int, by: str = "person", note: str = ""
) -> tuple[models.ReviewItem, list[int], int, str]:
    """Undo what the ticket claimed. Nothing is deleted, everything is reversed."""
    item = session.get(models.ReviewItem, item_id)
    if item is None:
        raise KeyError(item_id)
    if item.status is not models.ReviewStatus.open:
        raise AlreadyDecided(f"this item was already {item.status.value}")

    if item.kind is models.ReviewKind.donation:
        reversed_ids, difference, detail = _reject_donation(session, item)
    else:
        reversed_ids, difference, detail = _reject_posting(session, item)

    _mark(item, models.ReviewStatus.rejected, by, note)
    _record_correction(session, item, f"{item.kind.value} rejected", by)
    session.flush()
    return item, reversed_ids, difference, detail
