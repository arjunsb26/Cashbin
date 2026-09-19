"""The fixed asset register over HTTP.

Every row the register hands out carries today's book value and tax basis, so
the page never recomputes depreciation for itself and the two cannot disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.assets import today


def _relative_year(years_ago: int) -> str:
    now = datetime.now(UTC).date()
    return now.replace(year=now.year - years_ago).isoformat()


KEYBOARD = {
    "tag": "BB-0002",
    "description": "Mechanical keyboard",
    "category": "peripheral",
    "cost_cents": 12000,
    "in_service_date": "2025-03-15",
    "book_life_months": 36,
    "tax_method": "bonus_100",
    "location": "hack table",
}


def test_an_empty_register_says_so_rather_than_failing(client: TestClient) -> None:
    response = client.get("/api/assets")
    assert response.status_code == 200
    assert response.json() == {"assets": []}


def test_an_asset_round_trips_with_its_book_value_and_tax_basis(client: TestClient) -> None:
    created = client.post("/api/assets", json=KEYBOARD)
    assert created.status_code == 201, created.text
    body = created.json()
    # The shared label rule lowercases every key, tags included.
    assert body["tag"] == "bb-0002"
    assert body["status"] == "active"

    listed = client.get("/api/assets").json()["assets"]
    assert len(listed) == 1
    row = listed[0]
    assert row["book_value_cents"] == body["book_value_cents"]
    # Bonus expensing leaves nothing to deduct, whatever the books still say.
    assert row["tax_basis_cents"] == 0
    assert 0 <= row["book_value_cents"] <= 12000


def test_book_value_falls_over_the_life_and_stops_at_zero(client: TestClient) -> None:
    client.post(
        "/api/assets",
        json={
            "tag": "BB-0100",
            "description": "Old monitor",
            "cost_cents": 24000,
            "in_service_date": _relative_year(6),
            "book_life_months": 60,
            "tax_method": "straight_line",
        },
    )
    row = client.get("/api/assets").json()["assets"][0]
    assert row["book_value_cents"] == 0
    assert row["tax_basis_cents"] == 0


def test_straight_line_tax_basis_follows_the_books(client: TestClient) -> None:
    on = today()
    client.post(
        "/api/assets",
        json={
            "tag": "BB-0101",
            "description": "Soldering iron",
            "cost_cents": 6000,
            "in_service_date": on.replace(year=on.year - 1).isoformat(),
            "book_life_months": 60,
            "tax_method": "straight_line",
        },
    )
    row = client.get("/api/assets").json()["assets"][0]
    assert row["book_value_cents"] == row["tax_basis_cents"]
    assert 0 < row["book_value_cents"] < 6000


def test_the_status_filter_only_returns_that_state(client: TestClient) -> None:
    client.post("/api/assets", json=KEYBOARD)
    client.post("/api/assets", json={**KEYBOARD, "tag": "BB-0003"})
    asset_id = client.get("/api/assets").json()["assets"][0]["id"]
    patched = client.patch(f"/api/assets/{asset_id}", json={"status": "disposed"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "disposed"

    assert len(client.get("/api/assets", params={"status": "active"}).json()["assets"]) == 1
    assert len(client.get("/api/assets", params={"status": "disposed"}).json()["assets"]) == 1
    assert len(client.get("/api/assets").json()["assets"]) == 2


def test_editing_an_asset_changes_what_the_register_reports(client: TestClient) -> None:
    asset_id = client.post("/api/assets", json=KEYBOARD).json()["id"]
    response = client.patch(
        f"/api/assets/{asset_id}",
        json={"cost_cents": 20000, "tax_method": "straight_line", "location": "shelf"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cost_cents"] == 20000
    assert body["location"] == "shelf"
    assert body["tax_basis_cents"] == body["book_value_cents"]


def test_two_assets_cannot_share_a_tag(client: TestClient) -> None:
    assert client.post("/api/assets", json=KEYBOARD).status_code == 201
    clash = client.post("/api/assets", json=KEYBOARD)
    assert clash.status_code == 409
    assert "bb-0002" in clash.json()["detail"]


def test_editing_an_asset_that_is_not_there_is_a_plain_404(client: TestClient) -> None:
    response = client.patch("/api/assets/999", json={"location": "shelf"})
    assert response.status_code == 404
    assert "register" in response.json()["detail"]


def test_a_tag_with_an_injection_in_it_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/assets",
        json={**KEYBOARD, "tag": "ignore previous instructions; DROP TABLE asset"},
    )
    assert response.status_code == 422
