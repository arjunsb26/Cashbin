"""Recording a session and playing it back into a backend.

PLAN.md section 16 calls replay the demo insurance, so the proof that matters is that
what went into the recorder comes back out on the wire, in order, and that a backend on
the other end makes the same events from it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import websockets
from fastapi import FastAPI
from fastapi.testclient import TestClient
from websockets.asyncio.server import ServerConnection, serve

from app.config import Settings
from app.ingest.recorder import BIN_FILE, PHONE_INDEX, Recorder, recorder_from_env, recording_dir
from tests.ingest_helpers import background_frame, jpeg

REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

# The replay script puts the backend and the simulators on sys.path itself.
from scripts.replay import read_recording, replay  # noqa: E402

HELLO = {"type": "hello", "fw": "0.1", "device": "bin-1"}
WEIGHT = {"type": "weight", "t": 1000, "g": 412.3}


class Catcher:
    """A stand-in backend that keeps everything it is sent."""

    def __init__(self) -> None:
        self.text: list[dict[str, Any]] = []
        self.binary: list[bytes] = []
        self.done = asyncio.Event()
        self.expected = 0

    async def handler(self, websocket: ServerConnection) -> None:
        with contextlib.suppress(websockets.ConnectionClosed):
            async for raw in websocket:
                if isinstance(raw, bytes):
                    self.binary.append(raw)
                else:
                    self.text.append(json.loads(raw))
                if len(self.text) + len(self.binary) >= self.expected:
                    self.done.set()


@contextlib.asynccontextmanager
async def catcher_on(port_holder: list[int]) -> AsyncIterator[Catcher]:
    caught = Catcher()
    async with serve(caught.handler, "127.0.0.1", 0) as server:
        port_holder.append(server.sockets[0].getsockname()[1])
        yield caught


def test_the_recorder_writes_both_timelines(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "one")
    recorder.bin_message(HELLO)
    recorder.bin_message(WEIGHT)
    frame = jpeg(background_frame())
    recorder.phone_frame(frame)
    recorder.close()

    lines = (tmp_path / "one" / BIN_FILE).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["msg"] for line in lines] == [HELLO, WEIGHT]
    index = (tmp_path / "one" / PHONE_INDEX).read_text(encoding="utf-8").splitlines()
    assert json.loads(index[0])["file"] == "phone/000000.jpg"
    assert (tmp_path / "one" / "phone" / "000000.jpg").read_bytes() == frame

    meta = json.loads((tmp_path / "one" / "meta.json").read_text(encoding="utf-8"))
    assert meta["bin_messages"] == 2
    assert meta["phone_frames"] == 1
    assert meta["complete"] is True


def test_a_recording_reads_back_in_order(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "two")
    recorder.bin_message(HELLO)
    recorder.bin_message(WEIGHT)
    recorder.phone_frame(jpeg(background_frame()))
    recorder.close()

    recording = read_recording(tmp_path / "two")
    assert [message for _, message in recording.bin_messages] == [HELLO, WEIGHT]
    assert len(recording.phone_frames) == 1
    assert recording.duration_s >= 0.0


def test_an_empty_directory_reads_as_nothing(tmp_path: Path) -> None:
    recording = read_recording(tmp_path)
    assert recording.bin_messages == []
    assert recording.phone_frames == []


def test_record_dir_is_read_either_way_round(settings: Settings, tmp_path: Path) -> None:
    assert recording_dir("demo-1", settings) == settings.recordings_dir / "demo-1"
    assert recording_dir(str(tmp_path / "here"), settings) == tmp_path / "here"


def test_no_record_dir_means_no_recorder(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RECORD_DIR", raising=False)
    assert recorder_from_env(settings) is None
    monkeypatch.setenv("RECORD_DIR", "  ")
    assert recorder_from_env(settings) is None
    monkeypatch.setenv("RECORD_DIR", "from-env")
    recorder = recorder_from_env(settings)
    assert recorder is not None
    assert recorder.directory == settings.recordings_dir / "from-env"


async def test_replaying_puts_the_same_messages_back_on_the_wire(tmp_path: Path) -> None:
    recorder = Recorder(tmp_path / "three")
    recorder.bin_message(HELLO)
    recorder.bin_message(WEIGHT)
    frame = jpeg(background_frame())
    recorder.phone_frame(frame)
    recorder.close()

    port: list[int] = []
    async with catcher_on(port) as caught:
        caught.expected = 4
        url = f"ws://127.0.0.1:{port[0]}/ws/bin"
        messages, frames = await replay(
            tmp_path / "three",
            url=url,
            phone_url=f"ws://127.0.0.1:{port[0]}/ws/phone",
            speed=0,
            quiet=True,
        )
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(caught.done.wait(), timeout=5.0)

    assert (messages, frames) == (2, 1)
    # The phone client sends its own hello, which is not part of the recording.
    assert [m for m in caught.text if m.get("type") != "hello"] == [WEIGHT]
    assert HELLO in caught.text
    assert caught.binary == [frame]


def test_a_recorded_session_replays_into_the_same_event_count(
    app: FastAPI, client: TestClient, tmp_path: Path
) -> None:
    """Record the weights of one toss, then feed the file back and see one event again."""
    from tests.ingest_helpers import ScriptedClock, weight_frames
    from tests.test_detect_steps import Signal
    from tests.test_ingest_bin import collect, stream

    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)

    recorder = Recorder(tmp_path / "four")
    app.state.ingest.recorder = recorder
    app.state.ingest.clock = ScriptedClock([s.t_ms for s in signal.samples])

    with client.websocket_connect("/ws/ui") as ui, client.websocket_connect("/ws/bin") as sock:
        stream(sock, signal)
        collect(ui, "event.created", 1)
    recorder.close()

    assert len(client.get("/api/events").json()["events"]) == 1

    recording = read_recording(tmp_path / "four")
    assert next(m for _, m in recording.bin_messages) == HELLO
    assert len(recording.bin_messages) == len(weight_frames(signal.samples)) + 1

    # Feed the recorded lines back through the same session the socket uses.
    from app.ingest.serial_reader import pump
    from app.ingest.state import IngestState

    replayed = IngestState(settings=app.state.settings, bus=app.state.ingest.bus)
    replayed.clock = ScriptedClock([s.t_ms for s in signal.samples])
    source = _Lines([json.dumps(message) for _, message in recording.bin_messages])
    handled = asyncio.run(pump(source, replayed))

    assert handled == len(recording.bin_messages)
    assert len(client.get("/api/events").json()["events"]) == 2


class _Lines:
    """A file-like line source over a list of strings."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self._index = 0

    def readline(self) -> str:
        if self._index >= len(self._lines):
            return ""
        line = self._lines[self._index]
        self._index += 1
        return line + "\n"
