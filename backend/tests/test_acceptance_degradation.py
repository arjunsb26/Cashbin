"""PLAN.md rule 6, on the wire: what happens when a piece of the system is not there.

Three cases, each one a thing that will go wrong in a venue.

1. The cloud is unreachable. A toss ends in an ask inside the timeout and nothing raises.
2. The phone never connects. Tosses still weigh, and the ticket says its picture is poor.
3. The bin socket drops mid stream. The simulator reconnects, and the scale carries on.

No model is called. Case one points the real OpenAI adapter at a local port with nothing
listening, which is a refused connection rather than a request anybody pays for.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, reset_settings
from app.db import dispose_db, session_scope
from app.main import create_app
from app.models import CropQuality, Event, EventStatus, Identification
from app.notify.bus import reset_bus
from tests.ingest_helpers import ScriptedClock, weight_frames
from tests.test_detect_steps import Signal

HELLO = {"type": "hello", "fw": "0.1", "device": "bin-1"}

# A port on this machine with nothing behind it. Lane D is on 8000 and 8443 and the
# coordinator holds 3000 and 8444, so this one is out of everyone's way.
DEAD_PORT = 9001
DEAD_URL = f"http://127.0.0.1:{DEAD_PORT}/v1"

TIMEOUT_S = 4.0


def settings_for(tmp_path: Path, **extra: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "db_path": tmp_path / "binbooks.db",
        "media_dir": tmp_path / "media",
        "cert_dir": tmp_path / "certs",
        "recordings_dir": tmp_path / "recordings",
        "dev_tools": True,
        "seed_on_start": False,
    }
    base.update(extra)
    return Settings(**base)


@pytest.fixture
def unreachable_cloud(tmp_path: Path) -> Any:
    """A real OpenAI adapter aimed at a closed port. No key is ever used by anything."""
    conf = settings_for(
        tmp_path,
        llm_provider="openai",
        openai_api_key="not-a-real-key",
        llm_base_url=DEAD_URL,
        llm_timeout_s=TIMEOUT_S,
    )
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


@pytest.fixture
def plain(tmp_path: Path) -> Any:
    conf = settings_for(tmp_path)
    reset_settings(conf)
    reset_bus()
    yield conf
    dispose_db()
    reset_settings(Settings(_env_file=None))


def seed_catalog() -> None:
    import sys

    repo = Path(__file__).resolve().parents[2]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scripts.seed_db import seed_all

    with session_scope() as session:
        seed_all(session)


# 1. The cloud is not there -----------------------------------------------------


def test_a_dead_cloud_ends_in_an_ask_inside_the_timeout(unreachable_cloud: Settings) -> None:
    app = create_app(unreachable_cloud)
    with TestClient(app) as client:
        seed_catalog()
        assert app.state.pipeline.providers.name == "openai"

        started = time.perf_counter()
        posted = client.post(
            "/api/sim/toss", json={"label": "bagel", "mass_g": 95.0, "image": "bagel.png"}
        )
        elapsed = time.perf_counter() - started

        assert posted.status_code == 200, posted.text
        event_id = posted.json()["event_id"]
        assert posted.json()["status"] == EventStatus.asking
        assert elapsed < TIMEOUT_S * 2, f"the toss took {elapsed:.1f} s with nothing to call"

        detail = client.get(f"/api/events/{event_id}").json()
        assert detail["event"]["status"] == EventStatus.asking
        # The row says a call was tried and what served it. Nothing claims an answer.
        with session_scope() as session:
            rows = (
                session.query(Identification)
                .filter(Identification.event_id == event_id)
                .all()
            )
            assert rows
            assert all(not row.is_final for row in rows)
            assert all(row.label is None for row in rows)

        # And the backend is still answering.
        assert client.get("/api/health").status_code == 200
        second = client.post(
            "/api/sim/toss", json={"label": "cookie", "mass_g": 40.0, "image": "cookie.png"}
        )
        assert second.status_code == 200


# 2. The phone is not there -----------------------------------------------------


def test_a_bin_with_no_phone_still_makes_tickets(plain: Settings) -> None:
    app = create_app(plain)
    with TestClient(app) as client:
        seed_catalog()
        signal = Signal(seed=5)
        signal.hold(3.0)
        signal.add(95.0)
        signal.hold(2.5)
        app.state.ingest.clock = ScriptedClock([s.t_ms for s in signal.samples])
        client.post("/api/sim/expect", json={"label": "bagel"})

        with client.websocket_connect("/ws/bin") as bin_sock:
            bin_sock.send_json(HELLO)
            assert bin_sock.receive_json() == {"type": "ping"}
            for frame in weight_frames(signal.samples):
                bin_sock.send_json(frame)
            for _ in range(200):
                message = bin_sock.receive_json()
                if message.get("type") == "screen" and message.get("s") in {"result", "ask"}:
                    break

        rows = client.get("/api/events").json()["events"]
        assert rows, "the scale still makes events with no camera at all"
        ticket = rows[0]
        assert ticket["mass_g"] is not None
        assert ticket["crop_quality"] == CropQuality.low
        assert ticket["status"] in {EventStatus.posted, EventStatus.asking}


# 3. The bin socket drops -------------------------------------------------------


def test_a_bin_that_drops_mid_stream_comes_back_and_keeps_weighing(plain: Settings) -> None:
    app = create_app(plain)
    with TestClient(app) as client:
        seed_catalog()
        first = Signal(seed=6)
        first.hold(3.0)
        second = Signal(seed=6, start_g=0.0)
        second.hold(3.0)
        second.add(95.0)
        second.hold(2.5)

        app.state.ingest.clock = ScriptedClock([s.t_ms for s in first.samples])
        with client.websocket_connect("/ws/bin") as bin_sock:
            bin_sock.send_json(HELLO)
            assert bin_sock.receive_json() == {"type": "ping"}
            for frame in weight_frames(first.samples):
                bin_sock.send_json(frame)
        # The socket is gone. Nothing was ticketed, and the backend did not fall over.
        assert client.get("/api/events").json()["events"] == []
        assert client.get("/api/health").status_code == 200

        # The simulator reconnects and starts a fresh baseline, which is what the real
        # bridge script does. The step after it is detected normally.
        offset = first.samples[-1].t_ms + 1000.0
        app.state.ingest.clock = ScriptedClock([offset + s.t_ms for s in second.samples])
        client.post("/api/sim/expect", json={"label": "bagel"})
        with client.websocket_connect("/ws/bin") as bin_sock:
            bin_sock.send_json(HELLO)
            assert bin_sock.receive_json() == {"type": "ping"}
            for sample in second.samples:
                bin_sock.send_json(
                    {"type": "weight", "t": int(offset + sample.t_ms), "g": round(sample.g, 2)}
                )
            for _ in range(300):
                message = bin_sock.receive_json()
                if message.get("type") == "screen" and message.get("s") in {"result", "ask"}:
                    break

        rows = client.get("/api/events").json()["events"]
        assert len(rows) == 1, "the baseline recovered and the step after it was ticketed"
        assert abs((rows[0]["mass_g"] or 0.0) - 95.0) < 5.0
        with session_scope() as session:
            assert session.query(Event).count() == 1
