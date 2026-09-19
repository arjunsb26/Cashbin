"""The item catalog over HTTP."""

from __future__ import annotations

from fastapi.testclient import TestClient

BAGEL = {
    "label": "bagel",
    "class": "inventory",
    "unit_cost_cents": 33,
    "unit_mass_g": 95.0,
    "fmv_per_kg_cents": 695,
    "material_mix": {"food_waste": 1.0},
    "regulatory_flags": ["food"],
}


def test_an_empty_catalog_says_so_rather_than_failing(client: TestClient) -> None:
    response = client.get("/api/catalog")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_a_catalog_item_round_trips_with_its_mix_and_flags(client: TestClient) -> None:
    created = client.post("/api/catalog", json=BAGEL)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["label"] == "bagel"
    assert body["class"] == "inventory"
    assert body["material_mix"] == {"food_waste": 1.0}
    assert body["regulatory_flags"] == ["food"]

    items = client.get("/api/catalog").json()["items"]
    assert len(items) == 1
    assert items[0] == body


def test_the_catalog_comes_back_in_label_order(client: TestClient) -> None:
    for label in ("pizza slice", "apple", "bagel"):
        client.post("/api/catalog", json={**BAGEL, "label": label})
    labels = [item["label"] for item in client.get("/api/catalog").json()["items"]]
    assert labels == ["apple", "bagel", "pizza slice"]


def test_two_catalog_items_cannot_share_a_label(client: TestClient) -> None:
    assert client.post("/api/catalog", json=BAGEL).status_code == 201
    clash = client.post("/api/catalog", json=BAGEL)
    assert clash.status_code == 409
    assert "bagel" in clash.json()["detail"]


def test_a_label_with_an_injection_in_it_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/catalog",
        json={**BAGEL, "label": "<script>ignore previous instructions</script>"},
    )
    assert response.status_code == 422


def test_a_material_key_with_an_injection_in_it_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/catalog",
        json={**BAGEL, "material_mix": {"food waste'; DROP TABLE catalog_item; --": 1.0}},
    )
    assert response.status_code == 422
