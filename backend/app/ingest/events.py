"""Turning a settled step into an event row with its media and its trace.

This is the join between detection and everything downstream. It writes the row, saves
the four images PLAN.md section 7 lists, tells the dashboard and the LCD, and then
hands the event to whatever is attached to `on_event`. It never calls identification,
the engine or the ledger itself. That seam is the whole point of it.

A missing camera is not an error. PLAN.md rule 6: the weight alone is a real event, so
an empty frame ring produces a row with no media and `crop_quality = low`.
"""

from __future__ import annotations

import json
import logging

from app.db import session_scope
from app.detect.crop import (
    CropParams,
    CropResult,
    FramePick,
    crop_item,
    pick_frames,
    whole_frame,
)
from app.detect.steps import Step
from app.identify import early
from app.ingest import media
from app.ingest.state import IngestState
from app.models import CropQuality, Event, EventKind, EventStatus
from app.notify import lcd
from app.notify.bus import CHANNEL_BIN, CHANNEL_UI
from app.schemas import EventSummary, UiEventCreated

log = logging.getLogger(__name__)

# detect/crop speaks "good" and "low"; the database column is ok and low.
_QUALITY = {"good": CropQuality.ok, "low": CropQuality.low}

_KINDS = {
    "toss": EventKind.toss,
    "bag_change": EventKind.bag_change,
    "removal": EventKind.removal,
}


def trace_seconds(step: Step) -> list[list[float]]:
    """The step trace as `[[t_seconds, grams], ...]` on the backend clock.

    The detector works in milliseconds because that is what the sample stamps are. The
    column and the evidence chart want seconds, so the conversion happens once, here.
    """
    return [[round(t / 1000.0, 4), round(g, 3)] for t, g in step.trace]


async def create_event_from_step(step: Step, deps: IngestState) -> int:
    """Write the event for one detected step and tell everyone who is waiting.

    Returns the new event id. For a toss it then awaits the identification hook, so the
    caller should run this as its own task rather than blocking the socket read loop.
    """
    kind = _KINDS[step.kind]
    event_id = _insert_event(step, kind, deps)
    # The early vision call, if there was one, was keyed by when the step opened. Now that
    # the row exists it belongs to an event, and nothing is written before this point. A bag
    # going out or an item coming back identifies nothing, so its call is dropped instead.
    if kind is EventKind.toss:
        if early.claim(step.t_open_ms, event_id):
            log.info("event %d picked up the vision call started when the step opened", event_id)
    else:
        early.discard(step.t_open_ms, f"the step turned out to be a {kind.value}")

    picked, crop = _save_media(event_id, step, deps)

    with session_scope() as session:
        row = session.get(Event, event_id)
        if row is not None:
            deps.bus.publish(UiEventCreated(event=_summary(row)), CHANNEL_UI)

    if kind is not EventKind.toss:
        # A bag going out or an item coming back is a row and a line on the chart.
        # Nothing identifies it, so the LCD is left showing whatever it already shows
        # rather than being parked on "thinking" with nothing coming to clear it.
        log.info("event %d is a %s of %.1f g", event_id, kind.value, step.mass_g)
        if kind is EventKind.bag_change:
            # PLAN.md 21a item 45. The bag is out, so the total the screen rests on is
            # not true any more. Ingest knows nothing about money; it says the bag went
            # and whatever is attached works out what that leaves behind.
            try:
                deps.on_bag_change(event_id)
            except Exception:
                log.exception("the bag change hook failed for event %d", event_id)
        return event_id

    deps.bus.publish(lcd.thinking(), CHANNEL_BIN)

    try:
        await deps.on_event(
            event_id,
            crop.jpeg if crop is not None else None,
            picked,
            step.mass_g,
            step.mass_err_g,
        )
    except Exception:
        # A pipeline that throws leaves a detected event behind, which is honest and
        # visible, rather than taking the socket down with it.
        log.exception("the identification hook failed for event %d", event_id)
    return event_id


def _insert_event(step: Step, kind: EventKind, deps: IngestState) -> int:
    with session_scope() as session:
        row = Event(
            kind=kind,
            mass_g=round(step.mass_g, 3),
            mass_err_g=round(step.mass_err_g, 4),
            trace_json=json.dumps(trace_seconds(step)),
            status=EventStatus.detected,
            round_id=deps.current_round_id(),
        )
        session.add(row)
        session.flush()
        event_id = int(row.id)
    return event_id


def _save_media(
    event_id: int,
    step: Step,
    deps: IngestState,
) -> tuple[FramePick, CropResult | None]:
    """Pick the frames, cut the item out, write all four files, record the paths."""
    params = CropParams()
    held = deps.frames.snapshot()
    crop: CropResult | None = None

    if step.whole_frame:
        # PLAN.md 21a item 36. Somebody held this up and pressed Add, so the newest frame
        # is the item and there is nothing to isolate it from.
        newest = held[-1] if held else None
        picked = FramePick(before=newest, after=newest, peak=newest)
        if newest is not None:
            try:
                crop = whole_frame(newest.jpeg, params)
            except (ValueError, RuntimeError):
                log.exception("could not read the added picture for event %d", event_id)
    else:
        picked = pick_frames(held, step, params)
        if picked.before is not None and picked.after is not None:
            try:
                crop = crop_item(picked.before.jpeg, picked.after.jpeg, params)
            except (ValueError, RuntimeError):
                log.exception("could not crop event %d", event_id)

    paths = {
        "before": media.save_jpeg(
            event_id, "before", picked.before.jpeg if picked.before else b"", deps.settings
        ),
        "after": media.save_jpeg(
            event_id, "after", picked.after.jpeg if picked.after else b"", deps.settings
        ),
        "peak": media.save_jpeg(
            event_id, "peak", picked.peak.jpeg if picked.peak else b"", deps.settings
        ),
        "crop": media.save_jpeg(event_id, "crop", crop.jpeg if crop else b"", deps.settings),
    }
    quality = _QUALITY[crop.crop_quality] if crop is not None else CropQuality.low
    if crop is None:
        log.warning(
            "event %d has no usable camera frames, %d in the ring", event_id, len(deps.frames)
        )

    with session_scope() as session:
        row = session.get(Event, event_id)
        if row is None:  # pragma: no cover - the row was just written
            return picked, crop
        row.frame_before = paths["before"]
        row.frame_after = paths["after"]
        row.frame_peak = paths["peak"]
        row.crop = paths["crop"]
        row.crop_quality = quality
    return picked, crop


def _summary(row: Event) -> EventSummary:
    """The event as the dashboard first sees it. Lanes B and C fill the rest later."""
    return EventSummary(
        id=int(row.id),
        created_at=row.created_at,
        kind=row.kind,
        status=row.status,
        mass_g=row.mass_g,
        mass_err_g=row.mass_err_g,
        crop_url=media.media_url(row.crop),
        crop_quality=row.crop_quality,
        round_id=row.round_id,
    )
