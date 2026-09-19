"""Shared socket plumbing: one writer, one bus forwarder, one device status publisher.

Three tasks want to write to the same socket at once: the reply to whatever just came
in, the heartbeat, and anything published on the bus. They go through one `Outbox` so
sends are serialised and a socket that has gone away is noticed once rather than by
each of them separately.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from starlette.websockets import WebSocket, WebSocketState

from app.ingest.state import IngestState
from app.notify.bus import CHANNEL_UI, Subscription
from app.schemas import UiDeviceStatus

log = logging.getLogger(__name__)

HEARTBEAT_S = 2.0
SILENCE_S = 5.0


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Outbox:
    """Serialised writes to one websocket. Every send is best effort."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self._lock = asyncio.Lock()
        self.closed = False

    async def send(self, payload: dict[str, Any]) -> bool:
        if self.closed:
            return False
        async with self._lock:
            if self.websocket.client_state is not WebSocketState.CONNECTED:
                self.closed = True
                return False
            try:
                await self.websocket.send_json(payload)
            except (RuntimeError, OSError):
                self.closed = True
                return False
        return True

    async def send_model(self, message: BaseModel) -> bool:
        return await self.send(message.model_dump(mode="json"))

    async def close(self, code: int = 1000) -> None:
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(RuntimeError, OSError):
            await self.websocket.close(code=code)


async def forward(subscription: Subscription, out: Outbox) -> None:
    """Push everything on one subscription down one socket, until either one closes.

    The subscription is made before this task starts, so nothing published between the
    socket being accepted and the forwarder being scheduled is lost.
    """
    with contextlib.suppress(asyncio.CancelledError):
        async with subscription:
            async for message in subscription:
                if not await out.send_model(message):
                    return


async def heartbeat(
    out: Outbox,
    interval_s: float = HEARTBEAT_S,
    ready: asyncio.Event | None = None,
) -> None:
    """A ping every `interval_s`, once there is a session to check on.

    Nothing is sent before `ready`. A device that has not said hello yet is not allowed
    to send anything either, so pinging it first invites the one answer that gets it
    closed for a protocol violation. Replay hit exactly that.

    The firmware shows offline on its own after 5 s without a ping.
    """
    with contextlib.suppress(asyncio.CancelledError):
        if ready is not None:
            await ready.wait()
        while True:
            await asyncio.sleep(interval_s)
            if not await out.send({"type": "ping"}):
                return


def publish_device_status(
    deps: IngestState,
    device: Literal["bin", "phone"],
    connected: bool,
    detail: str | None = None,
) -> UiDeviceStatus:
    """Tell the dashboard a device came, went or went quiet, and remember it."""
    status = UiDeviceStatus(
        device=device,
        connected=connected,
        last_seen=now_iso(),
        detail=detail,
    )
    deps.note_device(status)
    deps.bus.publish(status, CHANNEL_UI)
    return status


async def cancel_all(tasks: list[asyncio.Task[None]]) -> None:
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
