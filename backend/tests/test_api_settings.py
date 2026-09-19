"""GET and PATCH /api/settings, and what they refuse to say."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import RUNTIME_SETTING_KEYS, Settings, get_settings
from app.db import session_scope
from app.models import Setting


def test_the_read_is_exactly_the_runtime_keys(client: TestClient, settings: Settings) -> None:
    body = client.get("/api/settings").json()
    assert set(body) == set(RUNTIME_SETTING_KEYS)
    assert body["confident_p"] == settings.confident_p
    assert body["round_size"] == settings.round_size


def test_nothing_about_the_model_or_the_key_is_readable(
    client: TestClient, settings: Settings
) -> None:
    settings.openai_api_key = "not-a-real-key"
    settings.llm_provider = "openai"
    settings.llm_base_url = "https://example.test/v1"
    body = client.get("/api/settings").json()
    text = json.dumps(body)
    for forbidden in ("openai_api_key", "llm_provider", "llm_base_url", "not-a-real-key"):
        assert forbidden not in text


def test_a_change_is_stored_and_applied_at_once(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"confident_p": 0.9, "min_margin": 0.4})
    assert response.status_code == 200
    assert response.json()["confident_p"] == 0.9
    assert response.json()["min_margin"] == 0.4

    # The running settings object is what the pipeline reads on the next event.
    assert get_settings().confident_p == 0.9
    with session_scope() as session:
        row = session.get(Setting, "confident_p")
        assert row is not None
        assert json.loads(row.value_json) == 0.9


def test_a_stored_change_is_applied_again_on_the_next_read(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        session.add(Setting(key="round_size", value_json="7"))
    assert client.get("/api/settings").json()["round_size"] == 7
    assert get_settings().round_size == 7


def test_a_value_outside_its_range_is_refused(client: TestClient) -> None:
    assert client.patch("/api/settings", json={"confident_p": 1.4}).status_code == 422
    assert client.patch("/api/settings", json={"round_size": 0}).status_code == 422
    assert client.patch("/api/settings", json={"tax_rate": -0.1}).status_code == 422


def test_a_key_that_is_not_a_runtime_setting_is_ignored(client: TestClient) -> None:
    response = client.patch(
        "/api/settings", json={"confident_p": 0.75, "openai_api_key": "not-a-real-key"}
    )
    assert response.status_code == 200
    assert "openai_api_key" not in response.json()
    assert get_settings().openai_api_key == ""
    with session_scope() as session:
        assert session.get(Setting, "openai_api_key") is None


def test_an_unreadable_stored_setting_is_skipped(client: TestClient) -> None:
    with session_scope() as session:
        session.add(Setting(key="confident_p", value_json="not json"))
    assert client.get("/api/settings").status_code == 200
