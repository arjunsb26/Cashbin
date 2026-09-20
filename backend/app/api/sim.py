"""Simulator control. Mounted only when DEV_TOOLS is on, so the demo build never shows it."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.config import REPO_DIR
from app.db import session_scope
from app.detect.crop import CropParams
from app.detect.steps import Step
from app.identify.stub import get_expect_queue
from app.ingest.events import create_event_from_step
from app.ingest.state import IngestState, get_ingest
from app.models import Event, EventStatus
from app.schemas import SimExpectRequest, SimExpectResponse, SimTossRequest, SimTossResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sim", tags=["sim"])

SIM_ASSETS = (REPO_DIR / "sim" / "assets").resolve()
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})

# The empty bin, which is what the camera was looking at a moment before the toss.
EMPTY_BIN_IMAGE = "bin.png"

# The shape of the fake step. Open a second before now so the ring has a before frame
# to reach back to, and settle just before now so the image pushed below counts as the
# after frame.
OPEN_LEAD_MS = 1000.0
SETTLE_LEAD_MS = 10.0
TRACE_RATE_HZ = 15.0


def asset_bytes(name: str) -> bytes | None:
    """Read one image out of `sim/assets`, or nothing.

    The name arrives in a request body, so it is treated as outside text: resolved
    against the assets directory and refused unless the result is still inside it with
    an image suffix. No traversal, no absolute path, no reading anything else on disk.
    """
    cleaned = name.strip().replace("\\", "/")
    if not cleaned or cleaned.startswith("/"):
        return None
    candidate = (SIM_ASSETS / cleaned).resolve()
    if not candidate.is_relative_to(SIM_ASSETS):
        log.warning("a sim toss asked for an image outside the assets directory")
        return None
    if candidate.suffix.lower() not in IMAGE_SUFFIXES or not candidate.is_file():
        return None
    try:
        return candidate.read_bytes()
    except OSError:
        log.exception("could not read the sim asset %s", candidate.name)
        return None


def synthetic_step(mass_g: float, now_ms: float) -> Step:
    """A step shaped like a real one: flat baseline, flat new level, no error to speak of.

    The trace runs from 2 s before the open to 1 s after the settle, which is the window
    PLAN.md section 7 stores, so the evidence chart of an injected toss looks like the
    evidence chart of a real one.
    """
    t_open = now_ms - OPEN_LEAD_MS
    t_settle = now_ms - SETTLE_LEAD_MS
    trace: list[list[float]] = []
    dt = 1000.0 / TRACE_RATE_HZ
    t = t_open - 2000.0
    while t <= t_settle + 1000.0:
        trace.append([round(t, 3), 0.0 if t < t_open else mass_g])
        t += dt
    return Step(
        kind="toss",
        t_open_ms=t_open,
        t_settle_ms=t_settle,
        mass_g=mass_g,
        mass_err_g=0.0,
        baseline_before_g=0.0,
        baseline_after_g=mass_g,
        trace=trace,
    )


def _push_empty_bin(deps: IngestState, now_ms: float) -> None:
    """Put an empty bin in the ring behind the injected frame.

    A crop is the difference between two frames, so one frame alone gives no crop, no
    exemplar and nothing for memory to recognise the next time the same thing goes in. A
    caller who hands this route an image is simulating the camera for this toss, so it gets
    the simulator's own background as the frame from a moment earlier, and the pair is the
    same pair every time that image is tossed. Leaving whatever the last toss left in the
    ring would diff one sprite against another and give a different crop each time.

    It lands exactly on the crop's own cutoff, which is the newest a before frame may be,
    so it wins over anything older without hiding anything the step itself needs.
    """
    empty = asset_bytes(EMPTY_BIN_IMAGE)
    if empty is None:
        log.warning("the simulator background is missing, the injected toss has no crop")
        return
    deps.frames.push(empty, now_ms - OPEN_LEAD_MS - CropParams().before_lead_ms)


@router.post("/toss", response_model=SimTossResponse)
async def inject_toss(body: SimTossRequest, request: Request) -> SimTossResponse:
    """Make one event without a scale. The dashboard demo path when no bin is plugged in."""
    deps: IngestState = get_ingest(request.app)
    now_ms = deps.clock()

    if body.image:
        data = asset_bytes(body.image)
        if data is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That image is not one of the simulator's.",
            )
        _push_empty_bin(deps, now_ms)
        deps.frames.push(data, now_ms)

    step = synthetic_step(body.mass_g, now_ms)
    log.info("injected a toss of %.1f g labelled %s", body.mass_g, body.label)
    event_id = await create_event_from_step(step, deps)

    # The hook has already run by here, so the status is whatever identification left,
    # not an assumption about it.
    with session_scope() as session:
        row = session.get(Event, event_id)
        current = row.status if row is not None else EventStatus.detected
    return SimTossResponse(event_id=event_id, status=current)


@router.post("/expect", response_model=SimExpectResponse)
def set_expected(body: SimExpectRequest) -> SimExpectResponse:
    """Queue what the simulator is about to toss, so the stub provider answers with it."""
    queued = get_expect_queue().push(str(body.label), body.mass_g)
    return SimExpectResponse(label=queued.label, mass_g=queued.mass_g)
