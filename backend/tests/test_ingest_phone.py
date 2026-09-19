"""`/ws/phone`: frames into the ring, and a toss that comes out with a picture."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest.frames import FrameRing
from app.models import CropQuality
from tests.ingest_helpers import (
    ScriptedClock,
    background_frame,
    frame_with_item,
    jpeg,
)
from tests.test_detect_steps import Signal
from tests.test_ingest_bin import collect, stream

PHONE_HELLO = {"type": "hello", "ua": "test phone"}


def test_binary_frames_land_in_the_ring(app: FastAPI, client: TestClient) -> None:
    background = jpeg(background_frame())
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json(PHONE_HELLO)
        assert socket.receive_json() == {"type": "ping"}
        for _ in range(3):
            socket.send_bytes(background)
        # The read loop is one loop in order, so a pong answered means the three
        # frames ahead of it have already been handled.
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        assert len(app.state.ingest.frames) == 3
        assert app.state.ingest.frames.latest().jpeg == background


def test_an_empty_binary_frame_is_ignored(app: FastAPI, client: TestClient) -> None:
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json(PHONE_HELLO)
        assert socket.receive_json() == {"type": "ping"}
        socket.send_bytes(b"")
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
        assert len(app.state.ingest.frames) == 0


def test_the_ring_only_keeps_its_window() -> None:
    ring = FrameRing(window_s=1.0)
    for index in range(20):
        ring.push(f"frame {index}".encode(), index * 100.0)
    assert ring.received == 20
    assert len(ring) == 11
    assert ring.snapshot()[0].t_ms == 900.0


def test_a_toss_with_camera_frames_writes_media(
    app: FastAPI, client: TestClient, settings: Settings
) -> None:
    """The whole lane in one test: frames, weight, crop, files on disk, row updated."""
    background = jpeg(background_frame())
    with_item = jpeg(frame_with_item(background_frame()))

    signal = Signal(seed=5).hold(3.0)
    signal.add(172.0)
    signal.hold(2.5)
    app.state.ingest.clock = ScriptedClock([s.t_ms for s in signal.samples])
    # A ring wide enough to hold the whole scripted run. The real one holds 4 s.
    app.state.ingest.frames = FrameRing(window_s=30.0)

    ring = app.state.ingest.frames
    for t_ms in range(0, 2400, 125):
        ring.push(background, float(t_ms))
    for t_ms in range(3900, 5500, 125):
        ring.push(with_item, float(t_ms))

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        created = collect(ui, "event.created", 1)[0]

    event_id = created["event"]["id"]
    assert created["event"]["crop_quality"] == CropQuality.ok
    assert created["event"]["crop_url"] == f"/media/{event_id}/crop.jpg"

    directory = Path(settings.media_dir) / str(event_id)
    written = sorted(path.name for path in directory.iterdir())
    assert written == ["after.jpg", "before.jpg", "crop.jpg", "peak.jpg"]
    assert (directory / "crop.jpg").stat().st_size > 0

    detail = client.get(f"/api/events/{event_id}").json()
    assert detail["frame_before_url"] == f"/media/{event_id}/before.jpg"
    assert detail["frame_after_url"] == f"/media/{event_id}/after.jpg"
    assert detail["frame_peak_url"] == f"/media/{event_id}/peak.jpg"
    assert client.get(detail["frame_before_url"]).status_code == 200

    # The crop is the item, not the whole frame.
    crop = (directory / "crop.jpg").read_bytes()
    assert len(crop) < len(with_item)


def test_the_hook_gets_the_crop(app: FastAPI, client: TestClient) -> None:
    seen: list[bytes | None] = []

    async def hook(
        event_id: int,
        crop: bytes | None,
        frames: object,
        mass_g: float,
        mass_err_g: float,
    ) -> None:
        seen.append(crop)

    background = jpeg(background_frame())
    with_item = jpeg(frame_with_item(background_frame()))
    signal = Signal(seed=5).hold(3.0)
    signal.add(172.0)
    signal.hold(2.5)
    app.state.ingest.clock = ScriptedClock([s.t_ms for s in signal.samples])
    app.state.ingest.frames = FrameRing(window_s=30.0)
    app.state.ingest.on_event = hook
    for t_ms in range(0, 2400, 125):
        app.state.ingest.frames.push(background, float(t_ms))
    for t_ms in range(3900, 5500, 125):
        app.state.ingest.frames.push(with_item, float(t_ms))

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as bin_sock:
        stream(bin_sock, signal)
        collect(ui, "event.created", 1)

    assert len(seen) == 1
    assert seen[0] is not None
    assert seen[0].startswith(b"\xff\xd8")


def test_the_phone_channel_reaches_the_phone(app: FastAPI, client: TestClient) -> None:
    from app.notify.bus import CHANNEL_PHONE
    from app.schemas import PhoneIdle

    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json(PHONE_HELLO)
        assert socket.receive_json() == {"type": "ping"}
        app.state.ingest.bus.publish(PhoneIdle(), CHANNEL_PHONE)
        assert socket.receive_json() == {"type": "idle"}


def test_two_phones_feed_one_ring(app: FastAPI, client: TestClient) -> None:
    """The ring is a view of the bin, not of a device. The demo has one phone anyway."""
    background = jpeg(background_frame())
    with client.websocket_connect("/ws/phone") as first:
        first.send_json(PHONE_HELLO)
        assert first.receive_json() == {"type": "ping"}
        with client.websocket_connect("/ws/phone") as second:
            second.send_json(PHONE_HELLO)
            assert second.receive_json() == {"type": "ping"}
            first.send_bytes(background)
            second.send_bytes(background)
            first.send_json({"type": "ping"})
            second.send_json({"type": "ping"})
            assert first.receive_json() == {"type": "pong"}
            assert second.receive_json() == {"type": "pong"}
            assert len(app.state.ingest.frames) == 2
            assert app.state.ingest.phone_count == 2
    assert app.state.ingest.phone_count == 0


def test_the_dashboard_hears_about_the_phone(client: TestClient) -> None:
    with client.websocket_connect("/ws/ui") as ui:
        with client.websocket_connect("/ws/phone") as socket:
            socket.send_json(PHONE_HELLO)
            assert socket.receive_json() == {"type": "ping"}
            status = ui.receive_json()
            assert status["device"] == "phone"
            assert status["connected"] is True
        assert ui.receive_json()["connected"] is False


def test_a_recorded_session_keeps_the_frames(
    app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    from app.ingest.recorder import Recorder

    recorder = Recorder(tmp_path / "session")
    app.state.ingest.recorder = recorder
    background = jpeg(background_frame())
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json(PHONE_HELLO)
        assert socket.receive_json() == {"type": "ping"}
        socket.send_bytes(background)
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
    assert recorder.frame_count == 1
    assert (tmp_path / "session" / "phone" / "000000.jpg").read_bytes() == background


def test_a_pong_from_the_phone_ends_the_exchange(client: TestClient) -> None:
    """Regression, the same loop as on the bin socket."""
    with client.websocket_connect("/ws/phone") as socket:
        socket.send_json(PHONE_HELLO)
        assert socket.receive_json() == {"type": "ping"}
        for _ in range(20):
            socket.send_json({"type": "pong"})
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}
