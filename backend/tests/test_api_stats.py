"""The stats route, and the paragraph written over it.

No live model is called anywhere here. The stub path is the deterministic join of
the suggestions, and the model path runs against a fake client.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.agent import prose, stats_summary
from app.config import Settings
from app.db import session_scope
from tests.test_ledger_stats import DAY_ONE, DAY_THREE, build_range


def _range() -> dict[str, str]:
    return {"from": DAY_ONE.isoformat(), "to": DAY_THREE.isoformat()}


def test_the_route_returns_a_bucket_a_day(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)

    body = client.get("/api/stats", params={**_range(), "bucket": "day"}).json()
    assert body["bucket"] == "day"
    assert body["period_start"] == "2026-09-14"
    assert [row["start"] for row in body["buckets"]] == [
        "2026-09-14", "2026-09-15", "2026-09-16"
    ]
    assert [row["tosses"] for row in body["buckets"]] == [3, 3, 4]
    assert body["averages"]["days"] == 3.0
    assert body["suggestions"]


def test_the_week_bucket_folds_the_range(client: TestClient, settings: Settings) -> None:
    with session_scope() as session:
        build_range(session)

    body = client.get("/api/stats", params={**_range(), "bucket": "week"}).json()
    assert len(body["buckets"]) == 1
    assert body["buckets"][0]["tosses"] == 10


def test_an_empty_range_says_so_without_inventing_anything(
    client: TestClient, settings: Settings
) -> None:
    body = client.get("/api/stats", params=_range()).json()
    assert [row["tosses"] for row in body["buckets"]] == [0, 0, 0]
    assert body["suggestions"] == []
    assert body["summary_md"] is None


def test_a_nonsense_range_does_not_break_the_route(
    client: TestClient, settings: Settings
) -> None:
    body = client.get("/api/stats", params={"from": "not-a-day", "to": "also-not"}).json()
    assert body["buckets"]
    assert body["bucket"] == "day"


def test_the_stub_paragraph_is_the_findings_joined(
    client: TestClient, settings: Settings
) -> None:
    with session_scope() as session:
        build_range(session)

    body = client.get("/api/stats", params=_range()).json()
    paragraph = body["summary_md"]
    assert paragraph is not None
    assert body["suggestions"][0] in paragraph
    assert len(prose.sentences(paragraph)) >= stats_summary.MIN_SENTENCES


# The model path, against a fake client -------------------------------------


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content
        self.tool_calls: list[Any] = []


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Reply:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = None


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[dict[str, Any]] = []

    def create(self, **request: Any) -> _Reply:
        self.requests.append(request)
        return _Reply(self.content)


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = type("chat", (), {"completions": FakeCompletions(content)})()

    @property
    def requests(self) -> list[dict[str, Any]]:
        completions: FakeCompletions = self.chat.completions
        return completions.requests


def _findings() -> tuple[list[str], dict[str, Any], dict[str, float]]:
    lines = [
        "Food is the biggest group at 11.92 dollars across 3 tickets.",
        "2 items nothing on the books tracked went in the bin, priced at 115.00 dollars.",
    ]
    totals = {"tosses": 10, "wasted_cents": 1192, "estimated_value_cents": 11500}
    averages = {"days": 3.0, "tosses_per_day": 3.333, "wasted_cents_per_day": 397.3}
    return lines, totals, averages


def test_the_model_paragraph_is_kept_when_every_figure_is_in_the_block(
    settings: Settings,
) -> None:
    lines, totals, averages = _findings()
    client = FakeClient(
        json.dumps(
            {
                "paragraph": (
                    "Food was the biggest group at 11.92 dollars over 3 tickets. "
                    "Two untracked items priced at 115.00 dollars went in the bin."
                )
            }
        )
    )
    found = stats_summary.write(settings, lines, totals, averages, client=client)
    assert found is not None
    assert "11.92" in found
    assert "115.00" in found

    request = client.requests[0]
    assert request["reasoning_effort"] == "low"
    assert request["response_format"]["json_schema"]["name"] == "stats_summary"


def test_a_sentence_with_a_number_nobody_computed_is_dropped(settings: Settings) -> None:
    lines, totals, averages = _findings()
    client = FakeClient(
        json.dumps(
            {
                "paragraph": (
                    "Food was the biggest group at 11.92 dollars over 3 tickets. "
                    "Two untracked items priced at 115.00 dollars went in the bin. "
                    "Waste is running at 48.50 dollars a week."
                )
            }
        )
    )
    found = stats_summary.write(settings, lines, totals, averages, client=client)
    assert found is not None
    assert "48.50" not in found


def test_an_advice_sentence_is_dropped(settings: Settings) -> None:
    lines, totals, averages = _findings()
    client = FakeClient(
        json.dumps(
            {
                "paragraph": (
                    "Food was the biggest group at 11.92 dollars over 3 tickets. "
                    "Two untracked items priced at 115.00 dollars went in the bin. "
                    "You should consider a smaller order to optimize this."
                )
            }
        )
    )
    found = stats_summary.write(settings, lines, totals, averages, client=client)
    assert found is not None
    assert "consider" not in found.lower()
    assert "should" not in found.lower()


def test_too_little_left_means_no_paragraph_at_all(settings: Settings) -> None:
    lines, totals, averages = _findings()
    client = FakeClient(
        json.dumps({"paragraph": "Waste is up 900.00 dollars and margins fell 12 percent."})
    )
    assert stats_summary.write(settings, lines, totals, averages, client=client) is None


def test_the_data_block_carries_the_findings_as_data(settings: Settings) -> None:
    lines, totals, averages = _findings()
    client = FakeClient(json.dumps({"paragraph": ""}))
    stats_summary.write(settings, lines, totals, averages, client=client)

    request = client.requests[0]
    system = request["messages"][0]["content"]
    block = request["messages"][1]["content"][1]["text"]
    assert "Do no arithmetic" in system
    assert json.loads(block)["findings"] == lines
