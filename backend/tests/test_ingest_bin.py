"""`/ws/bin` end to end: weight in, event rows out, dashboard and LCD told.

The staircase is the one `test_detect_steps` builds, so the detector is not being fed
anything kinder here than it is there. What is new is everything between the socket and
the database.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.config import Settings
from app.models import CropQuality, EventKind, EventStatus
from tests.ingest_helpers import ScriptedClock, weight_frames
from tests.test_detect_steps import Signal

HELLO = {"type": "hello", "fw": "0.1", "device": "bin-1"}
READ_CAP = 4000


def demo_signal() -> Signal:
    """Four tosses and a bag change, the demo scenario the sim plays."""
    signal = Signal(seed=11)
    signal.hold(3.0)
    for mass in (95.0, 780.0, 62.0, 172.0):
        signal.add(mass)
        signal.hold(2.5)
    signal.add(-1109.0)
    signal.hold(2.5)
    return signal


def drive(app: FastAPI, signal: Signal) -> None:
    """Point the ingest clock at the signal's own timeline."""
    app.state.ingest.clock = ScriptedClock([s.t_ms for s in signal.samples])


def collect(socket: WebSocketTestSession, topic: str, count: int) -> list[dict[str, Any]]:
    """Read from a socket until `count` messages of one type have arrived."""
    found: list[dict[str, Any]] = []
    for _ in range(READ_CAP):
        message = socket.receive_json()
        if message.get("type") == topic:
            found.append(message)
            if len(found) == count:
                return found
    raise AssertionError(f"only {len(found)} {topic} messages arrived, wanted {count}")


def stream(socket: WebSocketTestSession, signal: Signal) -> None:
    socket.send_json(HELLO)
    assert socket.receive_json() == {"type": "ping"}
    for frame in weight_frames(signal.samples):
        socket.send_json(frame)


def test_a_staircase_becomes_one_event_row_per_step(
    app: FastAPI, client: TestClient, settings: Settings
) -> None:
    signal = demo_signal()
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        created = collect(ui, "event.created", 5)

    assert [message["event"]["kind"] for message in created] == [
        EventKind.toss,
        EventKind.toss,
        EventKind.toss,
        EventKind.toss,
        EventKind.bag_change,
    ]

    rows = client.get("/api/events").json()["events"]
    assert len(rows) == 5
    masses = [row["mass_g"] for row in reversed(rows)]
    for got, wanted in zip(masses, [95.0, 780.0, 62.0, 172.0, -1109.0], strict=True):
        assert abs(got - wanted) < 3.0, f"{got} is not {wanted}"
    # Every toss goes the whole way now. A bag change identifies nothing, so it keeps the
    # status the event builder gave it.
    tosses = [row for row in rows if row["kind"] == EventKind.toss]
    assert {row["status"] for row in tosses} == {EventStatus.posted}
    changes = [row for row in rows if row["kind"] == EventKind.bag_change]
    assert {row["status"] for row in changes} == {EventStatus.detected}


def test_the_dashboard_sees_weight_and_the_event(app: FastAPI, client: TestClient) -> None:
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        weights = collect(ui, "weight", 3)
        created = collect(ui, "event.created", 1)[0]

    assert all(message["g"] is not None for message in weights)
    # One backend clock: the stamp is seconds on it, and the device millisecond is kept.
    assert weights[1]["t"] > weights[0]["t"]
    assert weights[0]["device_t"] is not None
    # Downsampled to 10 Hz from a 15 Hz stream, so consecutive stamps are 100 ms or more.
    assert weights[1]["t"] - weights[0]["t"] >= 0.0999
    assert created["event"]["id"] == 1
    assert created["event"]["status"] == EventStatus.detected


def test_the_weight_rate_on_the_dashboard_is_about_ten_a_second(
    app: FastAPI, client: TestClient
) -> None:
    """PLAN.md section 6: the dashboard topic is downsampled to 10 Hz."""
    signal = Signal(seed=5).hold(6.0)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        weights = collect(ui, "weight", 50)

    span_s = weights[-1]["t"] - weights[0]["t"]
    rate = (len(weights) - 1) / span_s
    assert 9.0 <= rate <= 11.0, f"the dashboard saw {rate:.1f} weight messages a second"


def test_a_toss_puts_thinking_on_the_lcd(app: FastAPI, client: TestClient) -> None:
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        collect(ui, "event.created", 1)
        screens = collect(bin_sock, "screen", 1)

    assert screens[0]["s"] == "thinking"


def test_a_bag_change_does_not_park_the_lcd_on_thinking(
    app: FastAPI, client: TestClient
) -> None:
    """Nothing identifies a bag change, so nothing would ever clear a thinking screen."""
    signal = Signal(seed=5, start_g=1200.0).hold(3.0)
    signal.add(-1109.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        created = collect(ui, "event.created", 1)[0]
        bin_sock.send_json({"type": "ping"})
        assert bin_sock.receive_json() == {"type": "pong"}

    assert created["event"]["kind"] == EventKind.bag_change


def test_an_event_with_no_camera_is_still_an_event(app: FastAPI, client: TestClient) -> None:
    """PLAN.md rule 6. No phone means a thin event, not a crash."""
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        collect(ui, "event.created", 1)

    detail = client.get("/api/events/1").json()
    assert detail["event"]["crop_quality"] == CropQuality.low
    assert detail["event"]["crop_url"] is None
    assert detail["frame_before_url"] is None
    assert len(detail["trace"]) > 10


def test_the_identification_hook_is_the_only_seam(app: FastAPI, client: TestClient) -> None:
    seen: list[tuple[int, bool, float]] = []

    async def hook(
        event_id: int,
        crop: bytes | None,
        frames: object,
        mass_g: float,
        mass_err_g: float,
    ) -> None:
        seen.append((event_id, crop is not None, mass_g))

    app.state.ingest.on_event = hook
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        collect(ui, "event.created", 1)

    assert len(seen) == 1
    event_id, has_crop, mass = seen[0]
    assert event_id == 1
    assert has_crop is False
    assert abs(mass - 95.0) < 3.0


def test_a_hook_that_throws_leaves_a_detected_event(app: FastAPI, client: TestClient) -> None:
    async def hook(
        event_id: int,
        crop: bytes | None,
        frames: object,
        mass_g: float,
        mass_err_g: float,
    ) -> None:
        raise RuntimeError("the pipeline fell over")

    app.state.ingest.on_event = hook
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)
    drive(app, signal)

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        collect(ui, "event.created", 1)
        collect(bin_sock, "screen", 1)
        bin_sock.send_json({"type": "ping"})
        assert bin_sock.receive_json() == {"type": "pong"}

    assert client.get("/api/events/1").json()["event"]["status"] == EventStatus.detected


def test_a_malformed_weight_is_dropped_not_fatal(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}
        socket.send_json({"type": "weight", "t": "soon", "g": "heavy"})
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_the_bin_channel_reaches_the_bin(client: TestClient) -> None:
    """Tare goes out on the bus and the socket forwards it. That is the LCD path too."""
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}
        assert client.post("/api/device/tare").json() == {"sent": True, "device": "bin"}
        assert socket.receive_json() == {"type": "tare"}


def test_tare_with_no_bin_says_so(client: TestClient) -> None:
    assert client.post("/api/device/tare").json()["sent"] is False


def test_the_dashboard_hears_about_the_bin(client: TestClient) -> None:
    with client.websocket_connect("/ws/ui") as ui:
        with client.websocket_connect("/ws/bin") as socket:
            socket.send_json(HELLO)
            assert socket.receive_json() == {"type": "ping"}
            status = ui.receive_json()
            assert status["type"] == "device.status"
            assert status["device"] == "bin"
            assert status["connected"] is True
        gone = ui.receive_json()
    assert gone["device"] == "bin"
    assert gone["connected"] is False


def test_a_dashboard_arriving_late_is_told_the_state(client: TestClient) -> None:
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}
        with client.websocket_connect("/ws/ui") as ui:
            first = ui.receive_json()
    assert first["type"] == "device.status"
    assert first == {
        "type": "device.status",
        "device": "bin",
        "connected": True,
        "last_seen": first["last_seen"],
        "detail": None,
    }


@pytest.mark.parametrize("junk", ["[]", '"hello"', "12"])
def test_json_that_is_not_an_object_is_answered_not_fatal(client: TestClient, junk: str) -> None:
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_text(junk)
        assert socket.receive_json() == {"type": "error", "detail": "not json"}


def test_a_pong_ends_the_exchange(client: TestClient) -> None:
    """Regression. A pong answered with a ping makes both ends flood the wire.

    The bin answers every ping with a pong, so one reply per pong is a loop that runs
    as fast as the socket allows. A 29 second scenario run recorded 40787 pongs before
    this was fixed. The heartbeat is the only thing that may start a ping.
    """
    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}
        for index in range(20):
            socket.send_json({"type": "pong", "t": index})
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_nothing_is_sent_before_the_hello(client: TestClient) -> None:
    """Regression from the first replay run.

    The heartbeat used to start the moment the socket opened, so a client that had not
    greeted yet got a ping, answered it, and was closed for talking before its hello.
    Replay opens its sockets before its first recorded message, so it hit this every
    time. Nothing goes out until the hello is in.
    """
    import time

    from app.ingest import wire

    with client.websocket_connect("/ws/bin") as socket:
        time.sleep(wire.HEARTBEAT_S + 0.5)
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}


def test_a_tare_is_written_down_so_the_close_can_use_it(client: TestClient) -> None:
    """Lane F concern 2. Without this row the close guesses the bin's zero."""
    from app.db import session_scope
    from app.ledger.close import TARE_SETTING_KEY
    from app.models import Setting

    with client.websocket_connect("/ws/bin") as socket:
        socket.send_json(HELLO)
        assert socket.receive_json() == {"type": "ping"}
        assert client.post("/api/device/tare").json()["sent"] is True
        assert socket.receive_json() == {"type": "tare"}

    with session_scope() as session:
        row = session.get(Setting, TARE_SETTING_KEY)
        assert row is not None
        stored = json.loads(row.value_json)
    assert stored["weight_g"] == 0.0
    assert stored["at"]


def test_a_tare_nobody_received_is_not_written_down(client: TestClient) -> None:
    from app.db import session_scope
    from app.ledger.close import TARE_SETTING_KEY
    from app.models import Setting

    assert client.post("/api/device/tare").json()["sent"] is False
    with session_scope() as session:
        assert session.get(Setting, TARE_SETTING_KEY) is None
