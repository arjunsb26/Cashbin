"""The ingest state one process shares: the frame ring, the clock, the seams.

Everything the sockets and the event builder need is here rather than in module
globals, so a test builds one of these and drives the whole path without a server, and
so two apps in one process never share a ring.

Two of the fields are seams for other lanes and default to doing nothing:

- `on_event` is where identification hangs. Lane C's pipeline is attached to it by the
  coordinator. Ingest never calls identification, the engine or the ledger itself.
- `current_round_id` answers which round an event belongs to. Lane C owns rounds, so
  until then it answers None and the column stays empty.
- `on_step_open` is where the early vision call hangs. The detector knows a step has
  started about a second before it knows what it weighs, and the picture is good long
  before that, so the glue starts the model then rather than after the settle.
- `on_bag_change` is where the running total hangs. The bag going out empties the bin, and
  the screen it rests on is the total of what is in the bag, so somebody has to be told.
  Ingest still identifies nothing and prices nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.ingest.clock import Clock, monotonic_ms
from app.ingest.frames import FrameRing
from app.ingest.recorder import Recorder, recorder_from_env
from app.notify.bus import Bus, get_bus
from app.schemas import UiDeviceStatus

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from app.detect.crop import FramePick

log = logging.getLogger(__name__)

DeviceName = str


class EventHook(Protocol):
    """What ingest hands the identification pipeline once an event row exists.

    `crop` is the cut-out item as JPEG bytes, or None when no camera frame was in the
    ring. `frames` carries the before, after and peak frames behind it. The crop
    quality that produced those bytes is on the event row.
    """

    async def __call__(
        self,
        event_id: int,
        crop: bytes | None,
        frames: FramePick,
        mass_g: float,
        mass_err_g: float,
    ) -> None: ...


def no_step_open(opened_ms: float, baseline_g: float) -> None:
    """The default step-open hook. Nothing starts early until a pipeline is attached."""
    log.debug("no pipeline attached, the step at %.0f ms waits for its settle", opened_ms)


async def no_pipeline(
    event_id: int,
    crop: bytes | None,
    frames: FramePick,
    mass_g: float,
    mass_err_g: float,
) -> None:
    """The default hook. Events stop at `detected` until a pipeline is attached."""
    log.debug("no identification pipeline attached, event %d stays detected", event_id)


def no_bag_change(event_id: int) -> None:
    """The default bag-change hook. Nothing resets until a pipeline is attached."""
    log.debug("no pipeline attached, the bag change on event %d tells nobody", event_id)


def no_round() -> int | None:
    """The default round source. Lane C replaces it when rounds exist."""
    return None


class IngestState:
    """One process worth of ingest. Held on `app.state.ingest`."""

    def __init__(
        self,
        settings: Settings | None = None,
        bus: Bus | None = None,
        clock: Clock = monotonic_ms,
        frames: FrameRing | None = None,
        recorder: Recorder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bus = bus or get_bus()
        self.clock: Clock = clock
        self.frames = frames or FrameRing()
        self.recorder = recorder
        self.on_event: EventHook = no_pipeline
        self.on_step_open: Callable[[float, float], None] = no_step_open
        self.on_bag_change: Callable[[int], None] = no_bag_change
        self.current_round_id: Callable[[], int | None] = no_round
        # The most recent reading off the scale, so the early call can say roughly how
        # heavy the thing is while the weight is still settling.
        self.latest_g = 0.0
        # Exactly one bin connection is current. A second one replaces it.
        self.bin_current: object | None = None
        self.phone_count = 0
        # Only devices that have been seen are in here. The dashboard treats a device
        # it has heard nothing about as not connected, which is what it is.
        self.device_status: dict[DeviceName, UiDeviceStatus] = {}

    def note_device(self, status: UiDeviceStatus) -> None:
        """Remember the latest status so a dashboard arriving later can be told it."""
        self.device_status[status.device] = status

    def close(self) -> None:
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None


def build_state(settings: Settings) -> IngestState:
    """What the lifespan builds. Switches the recorder on when RECORD_DIR is set."""
    return IngestState(settings=settings, recorder=recorder_from_env(settings))


def get_ingest(app: FastAPI) -> IngestState:
    """The app's ingest state, built on demand so a route never meets a missing one."""
    state: IngestState | None = getattr(app.state, "ingest", None)
    if state is None:
        state = build_state(getattr(app.state, "settings", None) or get_settings())
        app.state.ingest = state
    return state
