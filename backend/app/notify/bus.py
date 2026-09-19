"""In-process pub/sub between the pipeline and the sockets.

One publisher call reaches every dashboard and every phone that asked for that topic.
A subscriber that stops reading loses its oldest messages rather than stalling the pipeline,
because a live feed that blocks ingest is worse than a live feed that skips a frame.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable
from typing import Any

from pydantic import BaseModel

log = logging.getLogger(__name__)

CHANNEL_UI = "ui"
CHANNEL_PHONE = "phone"
CHANNEL_BIN = "bin"

DEFAULT_QUEUE_SIZE = 256


def topic_of(message: BaseModel) -> str:
    """Every wire message carries its topic in `type`, so the caller rarely names one."""
    value = getattr(message, "type", None)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{type(message).__name__} has no type field to use as a topic")
    return value


class Subscription:
    """One reader. Iterate it to receive messages until it is closed."""

    def __init__(
        self,
        bus: Bus,
        channel: str,
        topics: frozenset[str] | None,
        maxsize: int = DEFAULT_QUEUE_SIZE,
    ) -> None:
        self.bus = bus
        self.channel = channel
        self.topics = topics
        self.dropped = 0
        self._queue: asyncio.Queue[BaseModel | None] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    def wants(self, topic: str) -> bool:
        return self.topics is None or topic in self.topics

    def _offer(self, message: BaseModel) -> bool:
        """Never blocks. Drops the oldest message when the reader has fallen behind."""
        if self._closed:
            return False
        try:
            self._queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                return False
            try:
                self._queue.put_nowait(message)
                return True
            except asyncio.QueueFull:
                return False

    async def get(self) -> BaseModel | None:
        """Next message, or None once the subscription is closed."""
        return await self._queue.get()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.bus.unsubscribe(self)
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def __aenter__(self) -> Subscription:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        self.close()

    def __aiter__(self) -> AsyncIterator[BaseModel]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[BaseModel]:
        while True:
            message = await self.get()
            if message is None:
                return
            yield message


class Bus:
    """Subscribers grouped by channel. Publishing is synchronous and never awaits a reader."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscription]] = {}

    def subscribe(
        self,
        channel: str = CHANNEL_UI,
        topics: Iterable[str] | None = None,
        maxsize: int = DEFAULT_QUEUE_SIZE,
    ) -> Subscription:
        """Subscribe to one channel. Pass topics to narrow it, or leave it out for all of them."""
        sub = Subscription(
            self,
            channel,
            frozenset(topics) if topics is not None else None,
            maxsize=maxsize,
        )
        self._subscribers.setdefault(channel, []).append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        readers = self._subscribers.get(sub.channel)
        if readers and sub in readers:
            readers.remove(sub)

    def subscriber_count(self, channel: str | None = None) -> int:
        if channel is None:
            return sum(len(v) for v in self._subscribers.values())
        return len(self._subscribers.get(channel, []))

    def publish(
        self,
        message: BaseModel,
        channel: str = CHANNEL_UI,
        topic: str | None = None,
    ) -> int:
        """Deliver to every matching subscriber. Returns how many received it."""
        name = topic or topic_of(message)
        delivered = 0
        for sub in list(self._subscribers.get(channel, ())):
            if sub.wants(name) and sub._offer(message):
                delivered += 1
        return delivered

    def publish_many(
        self,
        message: BaseModel,
        channels: Iterable[str],
        topic: str | None = None,
    ) -> int:
        """Same message onto several channels, for example a result that both surfaces show."""
        return sum(self.publish(message, channel, topic) for channel in channels)

    def close(self) -> None:
        for readers in list(self._subscribers.values()):
            for sub in list(readers):
                sub.close()
        self._subscribers.clear()


_bus: Bus | None = None


def get_bus() -> Bus:
    """The process-wide bus. FastAPI routes and the pipeline both reach it through here."""
    global _bus
    if _bus is None:
        _bus = Bus()
    return _bus


def reset_bus() -> Bus:
    """Drop every subscriber and start a fresh bus. Tests call this between cases."""
    global _bus
    if _bus is not None:
        _bus.close()
    _bus = Bus()
    return _bus
