"""M2, on the wire: an unknown thing asks, an answer posts it, the next one is free.

PLAN.md section 20 M2. The check is not that the functions work, it is that a person
watching the bin, the phone and the dashboard all get asked the same question at the same
moment, that answering it on the REST surface posts the entry, and that the second time the
same object is tossed nothing is spent on it at all.

Everything here runs on the stub provider, so there is no key, no network and no cost.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from app.config import Settings, get_settings
from app.db import session_scope
from app.identify.embed import get_embedder
from app.learn.corrections import load_crop
from app.main import create_app
from app.models import (
    Event,
    EventStatus,
    Exemplar,
    Identification,
    IdentifyMethod,
    JournalBasis,
)

REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from scripts.seed_db import seed_all  # noqa: E402

# A shape the catalog has never seen, under a name the catalog does not hold. The stub is
# unsure about anything outside the catalog, which is the ask path without breaking a thing.
MYSTERY_IMAGE = "unknown.png"
MYSTERY_LABEL = "mystery widget"
MYSTERY_MASS_G = 150.0

# What a person answers with. A catalog label settles the class as well as the name, so the
# answer posts a real write-off rather than leaving an untracked object with no entry.
ANSWER = "bagel"

READ_CAP = 400


@pytest.fixture
def stocked_app(dev_settings: Settings) -> Any:
    """A dev backend with the catalog loaded and nothing else."""
    app = create_app(dev_settings)
    with TestClient(app) as client:
        with session_scope() as session:
            seed_all(session)
        yield app, client


def drain(socket: WebSocketTestSession, wanted: dict[str, int]) -> dict[str, list[Any]]:
    """Read one socket until every wanted topic has arrived, keeping what else turns up."""
    found: dict[str, list[Any]] = {topic: [] for topic in wanted}
    for _ in range(READ_CAP):
        message = socket.receive_json()
        topic = str(message.get("type"))
        if topic == "screen":
            topic = f"screen.{message.get('s')}"
        if topic in found:
            found[topic].append(message)
        if all(len(found[name]) >= need for name, need in wanted.items()):
            return found
    got = {name: len(found[name]) for name in wanted}
    raise AssertionError(f"the socket stopped short: {got} against {wanted}")


def test_an_unknown_thing_asks_everywhere_then_is_answered_and_remembered(
    stocked_app: Any,
) -> None:
    client: TestClient
    _app, client = stocked_app

    with (
        client.websocket_connect("/ws/ui") as ui,
        client.websocket_connect("/ws/phone") as phone,
        client.websocket_connect("/ws/bin") as bin_sock,
    ):
        bin_sock.send_json({"type": "hello", "fw": "0.1", "device": "bin-1"})
        assert bin_sock.receive_json() == {"type": "ping"}

        # One toss of a shape nobody has named, under a name nobody has taught.
        client.post("/api/sim/expect", json={"label": MYSTERY_LABEL})
        first = client.post(
            "/api/sim/toss",
            json={"label": MYSTERY_LABEL, "mass_g": MYSTERY_MASS_G, "image": MYSTERY_IMAGE},
        ).json()
        event_id = first["event_id"]
        assert first["status"] == EventStatus.asking

        # Channel one and two: the dashboard and the phone are asked the same question.
        seen_ui = drain(ui, {"ask.opened": 1})
        seen_phone = drain(phone, {"ask": 1})
        # Channel three: the bin shows the ask screen.
        seen_bin = drain(bin_sock, {"screen.ask": 1})

        assert seen_ui["ask.opened"][0]["event_id"] == event_id
        assert seen_phone["ask"][0]["event_id"] == event_id
        assert seen_ui["ask.opened"][0]["candidates"]
        assert seen_phone["ask"][0]["candidates"]
        assert seen_bin["screen.ask"][0]["s"] == "ask"

        # A person answers on the REST surface, and the entry is posted.
        answered = client.post(
            "/api/corrections",
            json={"event_id": event_id, "label": ANSWER, "by": "acceptance"},
        )
        assert answered.status_code == 200
        assert answered.json()["label"] == ANSWER

        detail = client.get(f"/api/events/{event_id}").json()
        assert detail["event"]["status"] == EventStatus.posted
        assert detail["event"]["label"] == ANSWER
        assert detail["entries"], "answering an ask has to post the entry"
        assert JournalBasis.book in {entry["basis"] for entry in detail["entries"]}
        for entry in detail["entries"]:
            debits = sum(line["debit_cents"] for line in entry["lines"])
            credited = sum(line["credit_cents"] for line in entry["lines"])
            assert debits == credited

        # The same shape again. Memory answers before anything is called or spent.
        second = client.post(
            "/api/sim/toss",
            json={"label": MYSTERY_LABEL, "mass_g": MYSTERY_MASS_G, "image": MYSTERY_IMAGE},
        ).json()
        repeat_id = second["event_id"]
        assert repeat_id != event_id
        assert second["status"] == EventStatus.posted

    with session_scope() as session:
        rows = (
            session.query(Identification)
            .filter(Identification.event_id == repeat_id)
            .order_by(Identification.id)
            .all()
        )
        assert rows, "the repeat toss left no identification row"
        final = [row for row in rows if row.is_final]
        assert len(final) == 1
        assert final[0].method is IdentifyMethod.memory
        assert final[0].label == ANSWER
        # PLAN.md section 9 item 2: memory costs nothing, and the row says so.
        assert final[0].cost_microusd == 0
        assert final[0].provider == "local"
        assert all(row.cost_microusd in (0, None) for row in rows)
        repeat_row = session.get(Event, repeat_id)
        assert repeat_row is not None
        assert repeat_row.status is EventStatus.posted

    # And the dashboard can see it was free.
    repeat = client.get(f"/api/events/{repeat_id}").json()
    methods = [row["method"] for row in repeat["identifications"]]
    assert IdentifyMethod.memory in methods
    assert IdentifyMethod.stub not in methods
    assert IdentifyMethod.cloud not in methods


def test_an_injected_toss_with_an_image_leaves_a_real_crop(stocked_app: Any) -> None:
    """The dashboard's own demo path has to produce the crop memory learns from.

    One frame is not a crop. Before the fix in `app/api/sim.py` an injected toss pushed
    only the item frame, so every ticket made this way came back `crop_quality` low with an
    empty crop file, no exemplar was ever stored, and the M2 check could not pass from the
    dashboard at all.
    """
    _app, client = stocked_app
    client.post("/api/sim/expect", json={"label": ANSWER})
    event_id = client.post(
        "/api/sim/toss", json={"label": ANSWER, "mass_g": 95.0, "image": "bagel.png"}
    ).json()["event_id"]

    body = client.get(f"/api/events/{event_id}").json()
    assert body["event"]["crop_url"]
    assert body["frame_before_url"] and body["frame_after_url"]

    with session_scope() as session:
        event = session.get(Event, event_id)
        assert event is not None
        crop = load_crop(get_settings(), event)
        assert crop, "the crop file is empty, so nothing can be remembered from it"
        assert get_embedder().embed(crop).size > 0
        exemplars = session.query(Exemplar).all()
        assert exemplars == [] or all(e.embedding for e in exemplars)
