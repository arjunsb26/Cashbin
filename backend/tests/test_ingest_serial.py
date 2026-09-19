"""The serial fallback reads the same JSON and reaches the same event builder.

PLAN.md section 5 makes the bin transport pluggable. The proof that it really is
pluggable is that a text stream with no websocket anywhere in it produces an event row
and gets a ping back, through the same `BinSession` the socket uses.
"""

from __future__ import annotations

import asyncio
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.ingest.serial_reader import PYSERIAL_HINT, open_serial_port, pump
from app.ingest.state import IngestState
from app.notify.bus import get_bus
from tests.ingest_helpers import ScriptedClock
from tests.test_detect_steps import Signal

HELLO = {"type": "hello", "fw": "0.1", "device": "bin-serial"}


def lines_for(signal: Signal) -> str:
    rows = [json.dumps(HELLO)]
    rows += [
        json.dumps({"type": "weight", "t": int(s.t_ms), "g": round(s.g, 2)})
        for s in signal.samples
    ]
    return "\n".join(rows) + "\n"


def test_json_lines_make_an_event(app: FastAPI, client: TestClient) -> None:
    signal = Signal(seed=5).hold(3.0)
    signal.add(95.0)
    signal.hold(2.5)

    deps = IngestState(settings=app.state.settings, bus=app.state.ingest.bus)
    deps.clock = ScriptedClock([s.t_ms for s in signal.samples])
    out = io.StringIO()

    handled = asyncio.run(pump(io.StringIO(lines_for(signal)), deps, out))

    assert handled == len(signal.samples) + 1
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies[0] == {"type": "ping"}

    events = client.get("/api/events").json()["events"]
    assert len(events) == 1
    assert abs(events[0]["mass_g"] - 95.0) < 3.0


def test_blank_lines_and_junk_do_not_stop_the_link(app: FastAPI, client: TestClient) -> None:
    deps = IngestState(settings=app.state.settings, bus=app.state.ingest.bus)
    source = io.StringIO(
        "\n".join(
            [
                json.dumps(HELLO),
                "",
                "not json at all",
                json.dumps({"type": "weight", "t": 1, "g": "heavy"}),
                json.dumps({"type": "pong", "t": 2}),
            ]
        )
        + "\n"
    )
    out = io.StringIO()
    handled = asyncio.run(pump(source, deps, out))

    assert handled == 4
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies[0] == {"type": "ping"}
    assert {"type": "error", "detail": "not json"} in replies
    # The hello ping and the junk error, and nothing for the pong. Answering a pong
    # with a ping is the loop the socket tests cover.
    assert len(replies) == 2


def test_traffic_before_a_hello_closes_the_link(settings: Settings) -> None:
    deps = IngestState(settings=settings, bus=get_bus())
    source = io.StringIO(json.dumps({"type": "weight", "t": 1, "g": 2.0}) + "\n" * 3)
    handled = asyncio.run(pump(source, deps))
    assert handled == 1


def test_a_line_cap_stops_early(settings: Settings) -> None:
    deps = IngestState(settings=settings, bus=get_bus())
    lines = "\n".join([json.dumps(HELLO)] * 5) + "\n"
    assert asyncio.run(pump(io.StringIO(lines), deps, max_lines=2)) == 2


def test_pyserial_is_optional(capsys: pytest.CaptureFixture[str]) -> None:
    """The project does not depend on pyserial. Missing it is a message, not a crash."""
    handle = open_serial_port("this-port-does-not-exist")
    if handle is None and PYSERIAL_HINT in capsys.readouterr().out:
        return
    # pyserial happens to be installed in this environment, so the call reached it.
    assert handle is None or hasattr(handle, "readline")
