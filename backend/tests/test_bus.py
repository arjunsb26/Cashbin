"""The in-process bus. One publish reaches every dashboard and every phone that wants it."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from app.notify.bus import CHANNEL_PHONE, CHANNEL_UI, Bus, Subscription, reset_bus, topic_of
from app.schemas import PhoneIdle, SummaryResponse, UiDeviceStatus, UiMetricsUpdated, UiWeight


@pytest.fixture
def bus() -> Bus:
    return reset_bus()


def _weight(g: float) -> UiWeight:
    return UiWeight(t=1.0, g=g)


async def _next(sub: Subscription) -> BaseModel:
    """Read one message and fail loudly if the subscription closed instead."""
    message = await sub.get()
    assert message is not None
    return message


def test_topic_comes_from_the_type_field() -> None:
    assert topic_of(_weight(1.0)) == "weight"
    assert topic_of(UiDeviceStatus(device="bin", connected=True)) == "device.status"


async def test_fan_out_reaches_every_subscriber(bus: Bus) -> None:
    first = bus.subscribe(CHANNEL_UI)
    second = bus.subscribe(CHANNEL_UI)

    assert bus.publish(_weight(412.3)) == 2

    assert await first.get() == _weight(412.3)
    assert await second.get() == _weight(412.3)


async def test_topic_filter_skips_the_uninterested(bus: Bus) -> None:
    weights = bus.subscribe(CHANNEL_UI, topics=["weight"])
    devices = bus.subscribe(CHANNEL_UI, topics=["device.status"])

    assert bus.publish(_weight(1.0)) == 1
    assert bus.publish(UiDeviceStatus(device="phone", connected=False)) == 1

    assert (await _next(weights)).model_dump()["type"] == "weight"
    assert (await _next(devices)).model_dump()["type"] == "device.status"


def test_channels_are_separate(bus: Bus) -> None:
    ui = bus.subscribe(CHANNEL_UI)
    phone = bus.subscribe(CHANNEL_PHONE)

    assert bus.publish(_weight(1.0), CHANNEL_UI) == 1
    assert bus.subscriber_count(CHANNEL_PHONE) == 1
    assert phone.pending() == 0
    assert ui.pending() == 1


def test_publish_many_hits_both_surfaces(bus: Bus) -> None:
    bus.subscribe(CHANNEL_UI)
    bus.subscribe(CHANNEL_PHONE)
    assert bus.publish_many(PhoneIdle(), [CHANNEL_UI, CHANNEL_PHONE]) == 2


def test_a_stalled_reader_loses_its_oldest_messages(bus: Bus) -> None:
    """A dashboard that stops reading must never stall ingest."""
    slow = bus.subscribe(CHANNEL_UI, maxsize=4)
    for i in range(10):
        bus.publish(_weight(float(i)))
    assert slow.dropped == 6
    assert slow.pending() == 4


async def test_a_dropping_reader_keeps_the_newest(bus: Bus) -> None:
    slow = bus.subscribe(CHANNEL_UI, maxsize=2)
    for i in range(5):
        bus.publish(_weight(float(i)))
    first = await _next(slow)
    second = await _next(slow)
    assert [first.model_dump()["g"], second.model_dump()["g"]] == [3.0, 4.0]


def test_close_removes_the_subscriber(bus: Bus) -> None:
    sub = bus.subscribe(CHANNEL_UI)
    assert bus.subscriber_count(CHANNEL_UI) == 1
    sub.close()
    assert bus.subscriber_count(CHANNEL_UI) == 0
    assert bus.publish(_weight(1.0)) == 0


async def test_iteration_ends_when_the_subscription_closes(bus: Bus) -> None:
    sub = bus.subscribe(CHANNEL_UI)
    received: list[float] = []

    async def read() -> None:
        async for message in sub:
            received.append(message.model_dump()["g"])

    task = asyncio.create_task(read())
    bus.publish(_weight(7.0))
    await asyncio.sleep(0)
    sub.close()
    await asyncio.wait_for(task, timeout=1.0)
    assert received == [7.0]


def test_publish_carries_a_whole_schema_object(bus: Bus) -> None:
    sub = bus.subscribe(CHANNEL_UI)
    message = UiMetricsUpdated(summary=SummaryResponse(events=3, kg_diverted=1.5))
    bus.publish(message)
    assert sub.take_nowait() is message


def test_a_message_without_a_type_is_refused(bus: Bus) -> None:
    with pytest.raises(ValueError, match="no type field"):
        bus.publish(SummaryResponse())
