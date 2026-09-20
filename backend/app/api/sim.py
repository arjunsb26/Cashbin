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


def synthetic_step(mass_g: float, now_ms: float, live: bool = False) -> Step:
    """A step shaped like a real one: flat baseline, flat new level, no error to speak of.

    The trace runs from 2 s before the open to 1 s after the settle, which is the window
    PLAN.md section 7 stores, so the evidence chart of an injected toss looks like the
    evidence chart of a real one.

    A live Add opens further back, so the frame picker reaches past the item being held up
    for its before frame instead of finding the item in both.
    """
    t_open = now_ms - (LIVE_BEFORE_MS if live else OPEN_LEAD_MS)
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


# How far back a live Add reaches for its "before" frame. Two seconds is long enough that
# whatever is being held up now was not in shot then, and short enough to still be in the
# four second ring.
LIVE_BEFORE_MS = 2000.0
NO_FRAMES = "No camera frames yet. Start the camera first."


def _live_step(deps: IngestState, now_ms: float) -> None:
    """Point the step at frames the camera has already sent, oldest one first.

    A crop is the difference between two frames. The newest frame is the item being held
    over the bin, and a frame about two seconds older is the bin without it. Both are
    already in the ring, so nothing is pushed and nothing is invented: the step is simply
    shaped to reach for them.
    """
    held = deps.frames.snapshot()
    if len(held) < 2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=NO_FRAMES)
    newest = held[-1]
    wanted = newest.t_ms - LIVE_BEFORE_MS
    older = min(held, key=lambda frame: abs(frame.t_ms - wanted))
    log.info(
        "an added item is cropped from the camera: %.0f ms apart, %d frames in the ring",
        newest.t_ms - older.t_ms,
        len(held),
    )


@router.post("/toss", response_model=SimTossResponse)
async def inject_toss(body: SimTossRequest, request: Request) -> SimTossResponse:
    """Make one event without a scale.

    Two ways in. With an image it is the simulator's own path, unchanged. Without one it is
    the Add button: a weight a person typed and whatever the camera can see right now.
    """
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
    else:
        _live_step(deps, now_ms)
        if body.label is not None:
            # Only the stub reads this, and only on this path: a caller driving the
            # simulator sets its own expectations with /api/sim/expect, and pushing
            # again behind them would leave one queued for the toss after this.
            get_expect_queue().push(str(body.label))

    step = synthetic_step(body.mass_g, now_ms, live=not body.image)
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
