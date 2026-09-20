"""`/ws/bin`: weight in, steps out, screens back down the same socket.

The protocol handling is in `BinSession` and knows nothing about websockets, because
PLAN.md section 5 makes the bin transport pluggable: the UNO Q bridge, a serial reader
on the laptop and the simulator all speak the same JSON and must all reach the same
code. `BinConnection` is that session wired to a websocket.

What the session does with a weight message:

1. Stamps it with the backend clock. The device `t` is carried along for debugging.
2. Feeds the step detector, whose tuning is read from the live settings.
3. Publishes `weight` to the dashboard at 10 Hz, not at the 15 to 20 Hz the scale sends.
4. On a settled step, builds the event in its own task so the stream never stalls.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.detect.steps import DetectParams, Sample, Step, StepDetector
from app.ingest import wire
from app.ingest.events import create_event_from_step
from app.ingest.state import IngestState, get_ingest
from app.notify.bus import CHANNEL_BIN, CHANNEL_UI
from app.schemas import BinButton, BinHello, BinPong, BinToBackend, BinWeight, UiWeight

log = logging.getLogger(__name__)

BIN_MESSAGE: TypeAdapter[BinToBackend] = TypeAdapter(BinToBackend)

# The dashboard chart is drawn at 10 Hz (PLAN.md section 6), whatever the scale sends.
UI_WEIGHT_PERIOD_MS = 100.0

Send = Callable[[dict[str, Any]], Awaitable[bool]]


def detect_params() -> DetectParams:
    """Detection tuning from the live settings, so /api/settings moves it without a restart."""
    conf = get_settings()
    return DetectParams(
        step_min_g=conf.step_min_g,
        settle_ms=float(conf.settle_ms),
        bag_change_g=conf.bag_change_g,
    )


class BinSession:
    """One bin conversation, independent of how the bytes arrive.

    `send` returns True while the far end is still there. Everything the session sends
    is a reply; screens and tare commands reach the bin through the `bin` bus channel
    and the transport forwards them.
    """

    def __init__(self, deps: IngestState, send: Send, source: str = "bin") -> None:
        self.deps = deps
        self.send = send
        self.source = source
        self.greeted = False
        self.device = ""
        self.detector = StepDetector(detect_params())
        self._tuning = _tuning_of(self.detector.params)
        self._next_ui_ms = float("-inf")
        self.samples = 0
        self.steps = 0
        self.pongs = 0
        self._tasks: set[asyncio.Task[int]] = set()

    async def handle_text(self, raw: str) -> bool:
        """Handle one text frame. False means the far end should be closed."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            await self.send({"type": "error", "detail": "not json"})
            return True
        if not isinstance(parsed, dict):
            await self.send({"type": "error", "detail": "not json"})
            return True
        return await self.handle_message(parsed)

    async def handle_message(self, parsed: dict[str, Any]) -> bool:
        """Every frame is validated. A hello that fails closes the socket; anything else
        that fails is logged and dropped, because one malformed reading is not a reason
        to take the bin off the air."""
        kind = parsed.get("type")
        if kind == "hello":
            return await self._hello(parsed)
        if not self.greeted:
            log.warning("%s sent %r before a hello", self.source, kind)
            return False
        if kind == "ping":
            # Not in the bin-to-backend union. The firmware is not meant to send one,
            # and answering it costs nothing if it ever does.
            await self.send({"type": "pong"})
            return True
        try:
            message = BIN_MESSAGE.validate_python(parsed)
        except ValidationError:
            log.warning("%s sent a %r message that does not validate", self.source, kind)
            return True
        if self.deps.recorder is not None:
            self.deps.recorder.bin_message(parsed)
        if isinstance(message, BinWeight):
            await self._weight(message)
        elif isinstance(message, BinPong):
            # A pong ends the exchange. Answering it with another ping makes the bin
            # answer that, and the two of them fill the wire as fast as the socket
            # allows: a 29 second scenario run produced 40787 pongs before this line
            # stopped replying. The heartbeat is the only thing that starts a ping.
            self.pongs += 1
        elif isinstance(message, BinButton):
            log.info("%s pressed button %s", self.source, message.id)
        return True

    async def _hello(self, parsed: dict[str, Any]) -> bool:
        try:
            hello = BinHello.model_validate(parsed)
        except ValidationError:
            log.warning("%s sent a hello that does not validate", self.source)
            return False
        self.greeted = True
        self.device = hello.device
        if self.deps.recorder is not None:
            self.deps.recorder.bin_message(parsed)
        log.info("%s said hello as %s on firmware %s", self.source, hello.device, hello.fw)
        await self.send({"type": "ping"})
        # The display's first screen is the running total, not "offline" until the first
        # toss. Found on the real board: it connected fine and sat on its startup screen
        # because nothing had been published to it yet.
        try:
            from app.db import session_scope
            from app.notify import lcd
            from app.pipeline import bin_total

            with session_scope() as session:
                total = bin_total(session)
            self.deps.bus.publish(
                lcd.idle_screen(total.cents, total.weight_g, total.count), CHANNEL_BIN
            )
        except Exception:
            log.exception("the idle screen could not be put up on hello")
        return True

    async def _weight(self, message: BinWeight) -> None:
        t_ms = self.deps.clock()
        self.samples += 1
        self._retune()

        if t_ms >= self._next_ui_ms:
            # Advance the slot rather than restarting the clock from this sample.
            # Waiting 100 ms from each published sample on a 15 Hz grid lands on
            # every second sample, which is 7.5 Hz, not the 10 Hz PLAN.md asks for.
            self._next_ui_ms += UI_WEIGHT_PERIOD_MS
            if self._next_ui_ms <= t_ms:
                self._next_ui_ms = t_ms + UI_WEIGHT_PERIOD_MS
            self.deps.bus.publish(
                UiWeight(t=round(t_ms / 1000.0, 4), g=message.g, device_t=message.t),
                CHANNEL_UI,
            )

        self.deps.latest_g = message.g
        was_open = self.detector.is_open
        step = self.detector.push(Sample(t_ms=t_ms, g=message.g))
        if not was_open and self.detector.is_open:
            self.on_step_open(t_ms)
        if step is not None:
            self.on_step(step)

    def on_step_open(self, t_ms: float) -> None:
        """A candidate step has started. Nothing is known about it yet except when.

        The detector will not call it a step until the weight has been stable for
        `settle_ms`, and the identification after that costs seconds more. The picture is
        already good, so the glue is told now and starts the model while the scale finishes.
        """
        baseline = self.detector.baseline_g or 0.0
        log.info("%s step opened at %.0f ms over a baseline of %.1f g", self.source, t_ms,
                 baseline)
        try:
            self.deps.on_step_open(t_ms, baseline)
        except Exception:
            log.exception("the step-open hook failed, the toss falls back to the settle")

    def on_step(self, step: Step) -> None:
        """Build the event off the read loop, so the weight stream keeps flowing.

        The step is copied first. The detector keeps appending the tail of the trace to
        the object it returned, and the event row wants the window as it was.
        """
        self.steps += 1
        snapshot = step.model_copy(deep=True)
        log.info(
            "%s step %d: %s of %.1f g +/- %.2f",
            self.source,
            self.steps,
            step.kind,
            step.mass_g,
            step.mass_err_g,
        )
        task = asyncio.create_task(create_event_from_step(snapshot, self.deps))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait for the events still being built. Used on shutdown and by tests."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def _retune(self) -> None:
        """Pick up a settings change, but never in the middle of an open step."""
        if self.detector.is_open:
            return
        params = detect_params()
        tuning = _tuning_of(params)
        if tuning == self._tuning:
            return
        self._tuning = tuning
        self.detector.params = params
        log.info("detection retuned to %s", tuning)


def _tuning_of(params: DetectParams) -> tuple[float, float, float]:
    return (params.step_min_g, params.settle_ms, params.bag_change_g)


class BinConnection:
    """`BinSession` on a websocket, plus the heartbeat, the bus and the device status."""

    def __init__(self, websocket: WebSocket, deps: IngestState) -> None:
        self.websocket = websocket
        self.deps = deps
        self.out = wire.Outbox(websocket)
        self.session = BinSession(deps, self.out.send, source="bin socket")
        self.greeted = asyncio.Event()
        self._last_seen = 0.0
        self._quiet = False

    async def run(self) -> None:
        await self.websocket.accept()
        subscription = self.deps.bus.subscribe(CHANNEL_BIN)
        if self.deps.bin_current is not None:
            log.warning("a second bin connected, it replaces the one already here")
        self.deps.bin_current = self
        wire.publish_device_status(self.deps, "bin", True)
        self._last_seen = asyncio.get_running_loop().time()

        tasks = [
            asyncio.create_task(wire.forward(subscription, self.out)),
            asyncio.create_task(wire.heartbeat(self.out, ready=self.greeted)),
            asyncio.create_task(self._watch_silence()),
        ]
        try:
            await self._read_loop()
        finally:
            await wire.cancel_all(tasks)
            subscription.close()
            await self.session.drain()
            if self.deps.bin_current is self:
                self.deps.bin_current = None
                wire.publish_device_status(self.deps, "bin", False, "the bin disconnected")

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self.websocket.receive_text()
                self._last_seen = asyncio.get_running_loop().time()
                if self._quiet:
                    self._quiet = False
                    wire.publish_device_status(self.deps, "bin", True)
                if not await self.session.handle_text(raw):
                    await self.out.close(code=1008)
                    return
                if self.session.greeted:
                    self.greeted.set()
                if self.out.closed:
                    return
        except WebSocketDisconnect:
            return
        except RuntimeError:
            # Starlette raises this when the socket is already gone.
            return

    async def _watch_silence(self) -> None:
        """Say so on the dashboard when the bin stops talking, without dropping it."""
        with contextlib.suppress(asyncio.CancelledError):
            while True:
                await asyncio.sleep(1.0)
                idle = asyncio.get_running_loop().time() - self._last_seen
                if idle >= wire.SILENCE_S and not self._quiet:
                    self._quiet = True
                    wire.publish_device_status(
                        self.deps,
                        "bin",
                        False,
                        f"no message for {int(idle)} s",
                    )


async def serve(websocket: WebSocket) -> None:
    """The `/ws/bin` route body."""
    await BinConnection(websocket, get_ingest(websocket.app)).run()
