"""GET /api/rules, the plain language and the citation behind every rule id."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine import rules as engine_rules


def test_every_rule_in_the_file_is_served(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    served = {row["id"] for row in body["rules"]}
    assert served == {rule.id for rule in engine_rules.all_rules()}
    assert len(served) >= 7


def test_a_rule_carries_the_words_and_the_link(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    abandon = next(row for row in body["rules"] if row["id"] == "ABANDON")
    assert abandon["title"] == "Abandoned business property"
    assert "ordinary loss" in abandon["plain_text"]
    assert abandon["citation_url"].startswith("https://www.irs.gov/")
    assert abandon["needs_human_review"] is False


def test_the_text_is_the_file_and_not_a_second_copy(client: TestClient) -> None:
    """The drawer reads the same words the engine cites. Nothing is retyped."""
    body = client.get("/api/rules").json()
    by_id = {row["id"]: row for row in body["rules"]}
    for rule in engine_rules.all_rules():
        assert by_id[rule.id]["plain_text"] == rule.plain_text
        assert by_id[rule.id]["title"] == rule.title
        assert by_id[rule.id]["citation_url"] == rule.citation_url


def test_a_rule_that_needs_a_person_says_so(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    flagged = [row["id"] for row in body["rules"] if row["needs_human_review"]]
    assert flagged, "at least one rule asks for a person to look"
