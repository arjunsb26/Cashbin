"""The vision call that was already running before the scale finished settling.

The wait a person feels runs from the item landing to the answer on the bin. Most of it is
two things in a row: the detector waiting `settle_ms` for the weight to be stable, and then
the model taking two to four seconds. They do not have to be in a row. The picture is good
about 300 ms after the item lands, so ingest starts the call there and this module holds the
work until identification asks for it.

One slot, because one bin has one open step at a time. Whoever takes it owns it. A step that
turns out to be a bag change or a removal cancels it, and a QR tag or a remembered exemplar
throws the answer away, because a call already on the wire cannot be unsent.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

from app.schemas import VisionResult

log = logging.getLogger(__name__)

# What the work gives back: the model's answer, and the crop it actually looked at.
EarlyResult = tuple[VisionResult | None, bytes | None]


@dataclass
class Pending:
    """One early call in flight, and the step it was started for."""

    opened_ms: float
    task: asyncio.Task[EarlyResult]
    event_id: int | None = field(default=None)

    async def result(self, timeout_s: float) -> EarlyResult:
        """What the model said, or (None, None) when it failed or ran out of time."""
        if self.task.cancelled():
            return None, None
        try:
            return await asyncio.wait_for(self.task, timeout=timeout_s)
        except TimeoutError:
            log.warning("the early vision call ran past %.1f s and was dropped", timeout_s)
        except asyncio.CancelledError:
            if not self.task.cancelled():
                raise
            log.info("the early vision call was cancelled before it answered")
        except Exception:
            log.exception("the early vision call failed")
        return None, None

    def cancel(self, why: str) -> None:
        if not self.task.done():
            self.task.cancel()
            log.info("the early vision call was dropped: %s", why)


# The one step that is open but has no event row yet, and the calls that have been given
# their event and are waiting to be collected.
_open: Pending | None = None
_claimed: dict[int, Pending] = {}
# A ceiling, so a call nobody ever collects cannot pile up.
KEEP_CLAIMED = 8


def start(opened_ms: float, work: Coroutine[Any, Any, EarlyResult]) -> Pending:
    """Run `work` now and hold it against the step that opened at `opened_ms`."""
    global _open
    if _open is not None:
        _open.cancel("a newer step opened before this one became an event")
    pending = Pending(opened_ms=opened_ms, task=asyncio.create_task(work))
    _open = pending
    return pending


def claim(opened_ms: float, event_id: int) -> bool:
    """Say which event the waiting call belongs to, now that the event row exists.

    Until this point the slot is keyed by when the step opened, because that is all that
    was known. A slot started for a different step is dropped rather than handed to the
    wrong ticket: an answer about the wrong object is worse than no answer.
    """
    global _open
    if _open is None:
        return False
    pending = _open
    _open = None
    if pending.opened_ms != opened_ms:
        pending.cancel("it was started for a different step")
        return False
    pending.event_id = event_id
    _claimed[event_id] = pending
    while len(_claimed) > KEEP_CLAIMED:
        stale_id, stale = next(iter(_claimed.items()))
        del _claimed[stale_id]
        stale.cancel(f"event {stale_id} never collected it")
    return True


def take(event_id: int) -> Pending | None:
    """Hand this event's waiting call to whoever is identifying, and empty the slot."""
    return _claimed.pop(event_id, None)


def discard(opened_ms: float, why: str) -> None:
    """Drop the call started for this step. The step turned out not to need one."""
    global _open
    if _open is not None and _open.opened_ms == opened_ms:
        _open.cancel(why)
        _open = None


def peek() -> Pending | None:
    """The call that is open and unclaimed, if there is one. Logging and tests."""
    return _open


def cancel(why: str) -> None:
    """Drop whatever is open and unclaimed. Safe to call when nothing is."""
    global _open
    if _open is not None:
        _open.cancel(why)
        _open = None


def clear() -> None:
    """Forget every slot without cancelling. Tests call this between cases."""
    global _open
    _open = None
    _claimed.clear()
