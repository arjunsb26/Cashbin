"""`/ws/phone`: camera frames in, results and asks out.

Binary frames are JPEG bytes and go straight into the ring buffer with a backend
arrival stamp. Text frames are the hello and the pong. Everything published on the
`phone` bus channel is forwarded down to the page, which is how a result or an ask
reaches the person holding the phone.

More than one phone may connect. They all feed the same ring, because the ring is a
view of the bin, not of a device. The demo has one phone.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import TypeAdapter, ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.ingest import wire
from app.ingest.state import IngestState, get_ingest
from app.notify.bus import CHANNEL_PHONE
from app.schemas import PhoneHello, PhoneToBackend

log = logging.getLogger(__name__)

PHONE_MESSAGE: TypeAdapter[PhoneToBackend] = TypeAdapter(PhoneToBackend)


class PhoneConnection:
    """One phone page on one socket."""

    def __init__(self, websocket: WebSocket, deps: IngestState) -> None:
        self.websocket = websocket
        self.deps = deps
        self.out = wire.Outbox(websocket)
        self.greeted = False
        self.frames = 0
        self.pongs = 0
        self.ready = asyncio.Event()

    async def run(self) -> None:
        await self.websocket.accept()
        subscription = self.deps.bus.subscribe(CHANNEL_PHONE)
        self.deps.phone_count += 1
        wire.publish_device_status(self.deps, "phone", True)

        tasks = [
            asyncio.create_task(wire.forward(subscription, self.out)),
            asyncio.create_task(wire.heartbeat(self.out, ready=self.ready)),
        ]
        try:
            await self._read_loop()
        finally:
            await wire.cancel_all(tasks)
            subscription.close()
            self.deps.phone_count = max(0, self.deps.phone_count - 1)
            if self.deps.phone_count == 0:
                wire.publish_device_status(
                    self.deps, "phone", False, "the camera page disconnected"
                )

    async def _read_loop(self) -> None:
        try:
            while True:
                packet = await self.websocket.receive()
                if packet.get("type") == "websocket.disconnect":
                    return
                raw = packet.get("text")
                if raw is None:
                    self._frame(packet.get("bytes") or b"")
                    continue
                if not await self._text(raw):
                    await self.out.close(code=1008)
                    return
                if self.greeted:
                    self.ready.set()
                if self.out.closed:
                    return
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return

    def _frame(self, data: bytes) -> None:
        if not data:
            return
        self.frames += 1
        self.deps.frames.push(data, self.deps.clock())
        if self.deps.recorder is not None:
            self.deps.recorder.phone_frame(data)

    async def _text(self, raw: str) -> bool:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            log.debug("phone sent text that is not json")
            return True
        if not isinstance(parsed, dict):
            return True
        kind = parsed.get("type")
        if kind == "hello":
            return await self._hello(parsed)
        if not self.greeted:
            log.warning("the phone sent %r before a hello", kind)
            return False
        if kind == "ping":
            await self.out.send({"type": "pong"})
            return True
        try:
            PHONE_MESSAGE.validate_python(parsed)
        except ValidationError:
            log.warning("the phone sent a %r message that does not validate", kind)
            return True
        if kind == "pong":
            # A pong ends the exchange. See the note in bin_socket: replying to one
            # with a ping makes the two ends flood each other.
            self.pongs += 1
        return True

    async def _hello(self, parsed: dict[str, Any]) -> bool:
        try:
            hello = PhoneHello.model_validate(parsed)
        except ValidationError:
            log.warning("the phone sent a hello that does not validate")
            return False
        self.greeted = True
        log.info("a camera page connected: %s", hello.ua[:60] or "no user agent")
        await self.out.send({"type": "ping"})
        return True


async def serve(websocket: WebSocket) -> None:
    """The `/ws/phone` route body."""
    await PhoneConnection(websocket, get_ingest(websocket.app)).run()
