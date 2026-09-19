"""`/ws/ui`: everything published on the `ui` channel, forwarded to the dashboard.

The dashboard never sends anything but a ping. On connect it is told the status of
every device the backend has heard from, so a page opened after the bin connected is
not left guessing.

A device the backend has never heard from is not mentioned. The dashboard draws a
device it has no status for as not connected, which is what it is, and saying so on
connect would be telling a page about hardware that has never existed.
"""

from __future__ import annotations

import asyncio
import json
import logging

from starlette.websockets import WebSocket, WebSocketDisconnect

from app.ingest import wire
from app.ingest.state import IngestState, get_ingest
from app.notify.bus import CHANNEL_UI

log = logging.getLogger(__name__)


class UiConnection:
    """One dashboard socket."""

    def __init__(self, websocket: WebSocket, deps: IngestState) -> None:
        self.websocket = websocket
        self.deps = deps
        self.out = wire.Outbox(websocket)

    async def run(self) -> None:
        await self.websocket.accept()
        subscription = self.deps.bus.subscribe(CHANNEL_UI)
        for status in list(self.deps.device_status.values()):
            await self.out.send_model(status)
        task = asyncio.create_task(wire.forward(subscription, self.out))
        try:
            await self._read_loop()
        finally:
            await wire.cancel_all([task])
            subscription.close()

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self.websocket.receive_text()
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                kind = parsed.get("type")
                if kind == "ping":
                    await self.out.send({"type": "pong"})
                elif kind == "pong":
                    await self.out.send({"type": "ping"})
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return


async def serve(websocket: WebSocket) -> None:
    """The `/ws/ui` route body."""
    await UiConnection(websocket, get_ingest(websocket.app)).run()
