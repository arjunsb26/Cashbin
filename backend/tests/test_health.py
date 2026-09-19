"""Health, the database, the static mounts, and the router stubs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.config import APP_VERSION, Settings
from app.db import get_engine, init_db
from app.models import ALL_TABLES, CHART_OF_ACCOUNTS


def test_health_says_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == APP_VERSION
    assert body["db"] is True
    assert body["product_name"] == "BinBooks"


def test_brand_is_served_and_not_cached(client: TestClient) -> None:
    response = client.get("/brand.json")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "name": "BinBooks",
        "short_name": "BinBooks",
        "tagline": "A trash can that does the books",
    }


def test_database_file_is_created(client: TestClient, settings: Settings) -> None:
    assert Path(settings.db_path).exists()


def test_every_table_from_the_plan_exists(client: TestClient) -> None:
    present = set(inspect(get_engine()).get_table_names())
    missing = sorted(set(ALL_TABLES) - present)
    assert not missing, f"missing tables: {missing}"


def test_sqlite_runs_in_wal_mode(client: TestClient) -> None:
    from sqlalchemy import text

    with get_engine().connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
    assert str(mode).lower() == "wal"


def test_chart_of_accounts_is_the_plan_list() -> None:
    assert set(CHART_OF_ACCOUNTS) == {
        "1200",
        "1500",
        "1590",
        "1000",
        "5100",
        "7200",
        "7210",
        "6400",
        "6800",
    }


def test_init_db_is_idempotent(settings: Settings) -> None:
    init_db(settings)
    init_db(settings)
    assert set(ALL_TABLES).issubset(set(inspect(get_engine()).get_table_names()))


# Routes still waiting for the lane that fills them. A lane deletes its line here in the
# same commit as the handler, so this list is always what is genuinely unbuilt.
STUB_ROUTES = [
    ("get", "/api/close/1"),
]

# Built routes answer 200 on an empty database.
BUILT_ROUTES = [
    ("get", "/api/assets"),
    ("get", "/api/catalog"),
    ("get", "/api/journal"),
    ("get", "/api/metrics/rounds"),
    ("post", "/api/metrics/rounds/start"),
    ("get", "/api/summary"),
    ("get", "/api/settings"),
]


@pytest.mark.parametrize(("method", "path"), STUB_ROUTES, ids=[f"{m}-{p}" for m, p in STUB_ROUTES])
def test_every_section_14_route_exists_and_says_not_built_yet(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path)
    assert response.status_code == 501, path
    assert response.json()["detail"].endswith("is not built yet.")
    # The lane that fills the route is named in a header, never in a body a person could read.
    assert response.headers["x-binbooks-owner"].startswith("Lane ")
    assert "Lane" not in response.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path"), BUILT_ROUTES, ids=[f"{m}-{p}" for m, p in BUILT_ROUTES]
)
def test_the_built_routes_answer(client: TestClient, method: str, path: str) -> None:
    assert getattr(client, method)(path).status_code == 200, path


def test_body_routes_exist(client: TestClient) -> None:
    correction = client.post("/api/corrections", json={"event_id": 1, "label": "bagel"})
    # No such ticket, which is a refusal a person can read, not a missing route.
    assert correction.status_code == 409
    assert (
        client.post(
            "/api/close", json={"period_start": "2026-09-01", "period_end": "2026-09-30"}
        ).status_code
        == 501
    )
    assert client.patch("/api/settings", json={"tax_rate": 0.25}).status_code == 200


def test_sim_routes_are_hidden_without_dev_tools(client: TestClient) -> None:
    """CLAUDE.md: dev-only surfaces are not rendered in the demo build."""
    assert client.post("/api/sim/toss", json={"label": "bagel", "mass_g": 90.0}).status_code == 404
    assert client.post("/api/sim/expect", json={"label": "bagel"}).status_code == 404


def test_sim_routes_appear_with_dev_tools(dev_client: TestClient) -> None:
    # Lane A filled /toss, so it answers. /expect is Lane C's and still says so.
    assert (
        dev_client.post("/api/sim/toss", json={"label": "bagel", "mass_g": 90.0}).status_code == 200
    )
    assert dev_client.post("/api/sim/expect", json={"label": "bagel"}).status_code == 200


def test_docs_are_hidden_without_dev_tools(client: TestClient, dev_client: TestClient) -> None:
    assert client.get("/api/openapi.json").status_code == 404
    assert dev_client.get("/api/openapi.json").status_code == 200


def test_media_is_mounted(client: TestClient) -> None:
    assert client.get("/media/nothing-here.jpg").status_code == 404


def test_a_bad_label_is_refused_before_the_handler(client: TestClient) -> None:
    """Validation runs at the boundary, so a hostile label never reaches a lane's code."""
    response = client.post("/api/corrections", json={"event_id": 1, "label": "<script>x</script>"})
    assert response.status_code == 422
