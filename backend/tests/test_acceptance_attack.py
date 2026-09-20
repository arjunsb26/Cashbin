"""The attack set on the wire, not at the function boundary.

CLAUDE.md names three places outside text reaches the system. `tests/test_injection.py`
proves the validator refuses each one. This file posts the same twenty five cases at the
running application over HTTP, and holds a sign up to the camera, because a wall that only
exists in a unit test is not a wall.

`POST /api/corrections` is the "Something else" answer. `POST /api/sim/expect` is the other
place a label is typed in. The photographed sign goes through the vision provider with a
hostile `visible_text` on every reply, and what has to come back is an ordinary ticket or an
ask, never a fixed asset worth nine thousand dollars.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import session_scope
from app.main import create_app
from app.models import Event, EventStatus, Identification, ItemClass, ItemRecord
from tests.attack_set import NORMALISE_CASES, REJECT_CASES, VISIBLE_TEXT_ATTACKS
from tests.test_acceptance_m4 import ScriptedOpenAI, soak_settings  # noqa: F401

REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from scripts.seed_db import seed_all  # noqa: E402

UNKNOWN_MASS_G = 150.0

# One sprite per case. An answered case leaves an exemplar behind, and the next toss of the
# same picture would then be recognised from memory instead of opening the ask this file
# needs. A different picture each time keeps every case honest.
IMAGES = (
    "unknown.png",
    "banana.png",
    "earbuds.png",
    "mouse.png",
    "cookie.png",
    "pizza_slice.png",
    "plastic_cup.png",
    "usb_cable.png",
    "wrap.png",
    "chips.png",
    "soda_can.png",
    "paper_cup.png",
    "water_bottle.png",
    "cardboard.png",
    "pasta.png",
)


@pytest.fixture
def attack_client(dev_settings: Settings) -> Any:
    app = create_app(dev_settings)
    with TestClient(app) as client:
        with session_scope() as session:
            seed_all(session)
        yield client


def open_an_ask(client: TestClient, index: int = 0) -> int:
    """One event sitting at `asking`, ready for a hostile answer."""
    client.post("/api/sim/expect", json={"label": "mystery widget"})
    body = client.post(
        "/api/sim/toss",
        json={
            "label": "mystery widget",
            "mass_g": UNKNOWN_MASS_G,
            "image": IMAGES[index % len(IMAGES)],
        },
    ).json()
    assert body["status"] == EventStatus.asking
    return int(body["event_id"])


# The ask answer ---------------------------------------------------------------
#
# One client serves every case. A client per case would open a hundred loopback socket
# pairs on a machine that has a hundred of its ephemeral ports reserved by Windows, and the
# suite then fails on ports rather than on anything this file is about.


def test_every_hostile_answer_is_refused_by_the_running_api(attack_client: TestClient) -> None:
    for index, (name, raw) in enumerate(REJECT_CASES):
        event_id = open_an_ask(attack_client, index)
        response = attack_client.post(
            "/api/corrections", json={"event_id": event_id, "label": raw, "by": "attacker"}
        )
        assert response.status_code == 422, name
        body = json.dumps(response.json())
        assert raw.strip() == "" or raw[:60] not in body, (
            f"{name}: the refusal echoed the payload back"
        )

        with session_scope() as session:
            event = session.get(Event, event_id)
            assert event is not None
            assert event.status is EventStatus.asking, f"{name}: a refused answer changed the row"
            assert session.get(ItemRecord, event_id) is None, name


def test_every_survivable_answer_lands_as_a_plain_key(attack_client: TestClient) -> None:
    for index, (name, raw, expected) in enumerate(NORMALISE_CASES):
        event_id = open_an_ask(attack_client, index)
        response = attack_client.post(
            "/api/corrections", json={"event_id": event_id, "label": raw, "by": "attacker"}
        )
        assert response.status_code == 200, name
        assert response.json()["label"] == expected, name

        detail = attack_client.get(f"/api/events/{event_id}").json()
        assert detail["event"]["label"] == expected, name
        assert detail["event"]["status"] == EventStatus.posted, name
        with session_scope() as session:
            stored = (
                session.query(Identification.label)
                .filter(Identification.event_id == event_id, Identification.is_final.is_(True))
                .scalar()
            )
            assert stored == expected, name
            record = session.get(ItemRecord, event_id)
            assert record is not None, name
            # An answer nobody recognises is an untracked object. It never promotes itself.
            assert record.item_class is not ItemClass.fixed_asset, name
            assert record.asset_id is None, name


# The other place a label is typed ---------------------------------------------


def test_every_hostile_expectation_is_refused(attack_client: TestClient) -> None:
    for name, raw in REJECT_CASES:
        response = attack_client.post("/api/sim/expect", json={"label": raw})
        assert response.status_code == 422, name
        assert raw.strip() == "" or raw[:60] not in json.dumps(response.json()), name


def test_every_survivable_expectation_is_normalised(attack_client: TestClient) -> None:
    for name, raw, expected in NORMALISE_CASES:
        response = attack_client.post("/api/sim/expect", json={"label": raw})
        assert response.status_code == 200, name
        assert response.json()["label"] == expected, name


# The sign in the photograph ----------------------------------------------------


def test_a_sign_held_up_to_the_camera_ends_in_a_normal_ticket(
    soak_settings: Settings,  # noqa: F811
) -> None:
    """The model reads the sign back. The system treats it as something it saw, not as told."""
    app = create_app(soak_settings)
    fake = ScriptedOpenAI()
    fake.completions.label = "cardboard box small"
    fake.completions.known = True
    with TestClient(app) as client:
        with session_scope() as session:
            seed_all(session)
        app.state.pipeline.vision.inner._client = fake
        app.state.pipeline.providers.estimator._client = fake

        for index, raw in enumerate(VISIBLE_TEXT_ATTACKS):
            fake.completions.visible_text = raw
            body = client.post(
                "/api/sim/toss",
                json={"label": "cardboard", "mass_g": 220.0, "image": "cardboard.png"},
            ).json()
            event_id = body["event_id"]
            assert body["status"] in {EventStatus.posted, EventStatus.asking}, index

            detail = client.get(f"/api/events/{event_id}").json()
            record = detail["item_record"]
            if record is not None:
                assert record["class"] != ItemClass.fixed_asset, index
                assert record["label"] == "cardboard box small", index
                assert record["book_value_cents"] == 0, index
                assert record["asset_id"] is None, index
            # Nothing on the ticket repeats the sign, and nothing came off the register.
            assert raw[:40].lower() not in json.dumps(detail).lower(), index
            assert client.get("/api/assets").json()["assets"] == [], index
