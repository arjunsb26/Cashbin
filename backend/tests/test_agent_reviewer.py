"""The review agent: it looks things up, proposes, and cannot act.

The model path runs against a fake client that makes two tool calls and then
answers, which is the shape of a real run. No live call is made anywhere.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import models
from app.agent import review_tools, reviewer
from app.config import Settings
from app.db import session_scope
from app.ledger import review
from tests.test_ledger_review import _donation_ticket, _event, _option, _record


def _item(settings: Settings) -> int:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        made = review.create_for_event(session, event_id, settings)
        session.commit()
        return made[0].id


# The tools -----------------------------------------------------------------


def test_get_event_returns_the_whole_ticket(settings: Settings) -> None:
    with session_scope() as session:
        event_id = _donation_ticket(session)
        found = review_tools.get_event(session, event_id)

    assert found["item"]["label"] == "bagel"
    assert found["item"]["class"] == "inventory"
    assert len(found["options"]) == 2
    assert found["entries"]


def test_get_rule_reads_the_rules_file(settings: Settings) -> None:
    found = review_tools.get_rule("DONATE_FOOD")
    assert found["needs_human_review"] is True
    assert "cost plus half the mark up" in found["plain_text"]

    unknown = review_tools.get_rule("NOT_A_RULE")
    assert unknown["error"] == "no such rule"
    assert "ABANDON" in unknown["rule_ids"]


def test_find_similar_shows_how_the_same_label_went_before(settings: Settings) -> None:
    with session_scope() as session:
        first = _donation_ticket(session)
        made = review.create_for_event(session, first, settings)
        session.commit()
        review.approve(session, made[0].id, "nishad", "")
        session.commit()
    with session_scope() as session:
        _donation_ticket(session)
        found = review_tools.find_similar(session, "bagel", 90)

    assert found["count"] == 2
    decided = [row for row in found["rows"] if row["review_status"] == "approved"]
    assert len(decided) == 1


def test_get_policy_carries_the_thresholds(settings: Settings) -> None:
    with session_scope() as session:
        found = review_tools.get_policy(session, settings)

    assert found["capitalization_threshold_cents"] == 50_000
    assert found["review_after_s"] == 120.0
    assert "catalog_median_cents_by_class" in found


def test_an_unknown_tool_is_an_answer_not_a_crash(settings: Settings) -> None:
    with session_scope() as session:
        found = review_tools.run_tool(session, settings, "drop_table", {})
    assert found["error"] == "no such tool"


def test_bad_arguments_are_an_answer_not_a_crash(settings: Settings) -> None:
    with session_scope() as session:
        found = review_tools.run_tool(
            session, settings, review_tools.GET_EVENT, {"event_id": "; DROP TABLE event"}
        )
    assert "not readable" in found["error"]


# The stub path -------------------------------------------------------------


def test_the_stub_proposal_shows_the_lookups_it_made(settings: Settings) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings)

    assert found.decision == reviewer.DECISION_ASK
    assert [step.tool for step in found.steps] == [
        review_tools.GET_EVENT,
        review_tools.GET_POLICY,
    ]
    assert found.reason
    assert found.steps[0].finding


def test_the_proposal_is_stored_and_nothing_is_decided(settings: Settings) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        reviewer.attach(session, item, settings)
        session.commit()

    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        assert item.status is models.ReviewStatus.open
        assert item.proposal_json
        assert reviewer.stored(item) is not None


# The model path, against a fake client -------------------------------------


class _Function:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _Call:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.function = _Function(name, arguments)


class _Message:
    def __init__(self, content: str, calls: list[_Call] | None = None) -> None:
        self.content = content
        self.tool_calls = calls or []


class _Choice:
    def __init__(self, message: _Message) -> None:
        self.message = message


class _Reply:
    def __init__(self, message: _Message) -> None:
        self.choices = [_Choice(message)]
        self.usage = None


class ToolLoopCompletions:
    """Two tool calls, then the answer. The shape of a real run."""

    def __init__(self, answer: dict[str, Any], event_id: int) -> None:
        self.answer = answer
        self.event_id = event_id
        self.requests: list[dict[str, Any]] = []
        self.turn = 0

    def create(self, **request: Any) -> _Reply:
        self.requests.append(request)
        self.turn += 1
        if self.turn == 1:
            return _Reply(
                _Message(
                    "",
                    [
                        _Call(
                            "a",
                            review_tools.GET_EVENT,
                            json.dumps({"event_id": self.event_id}),
                        )
                    ],
                )
            )
        if self.turn == 2:
            return _Reply(
                _Message("", [_Call("b", review_tools.GET_RULE, '{"rule_id": "DONATE_FOOD"}')])
            )
        return _Reply(_Message(json.dumps(self.answer)))


class ToolLoopClient:
    def __init__(self, answer: dict[str, Any], event_id: int) -> None:
        self.chat = type(
            "chat", (), {"completions": ToolLoopCompletions(answer, event_id)}
        )()

    @property
    def calls(self) -> ToolLoopCompletions:
        return self.chat.completions  # type: ignore[no-any-return]


def _event_id_of(session: Session, item_id: int) -> int:
    item = session.get(models.ReviewItem, item_id)
    assert item is not None
    return item.event_id


def test_the_agent_calls_two_tools_then_answers(settings: Settings) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        event_id = _event_id_of(session, item_id)
        client = ToolLoopClient(
            {
                "decision": "reject",
                "reason": "The bagel cost 100 cents and the charity is not confirmed.",
                "evidence": ["The ticket is inventory with 100 cents of cost."],
            },
            event_id,
        )
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings, client=client)

    assert found.decision == "reject"
    assert [step.tool for step in found.steps] == [
        review_tools.GET_EVENT,
        review_tools.GET_RULE,
    ]
    assert found.steps[1].args_summary == "rule_id=DONATE_FOOD"
    assert found.tool_calls == 2
    assert client.calls.requests[0]["reasoning_effort"] == "low"
    assert len(client.calls.requests[0]["tools"]) == 6


def test_a_reason_citing_a_figure_no_tool_returned_is_replaced(
    settings: Settings,
) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        event_id = _event_id_of(session, item_id)
        client = ToolLoopClient(
            {
                "decision": "approve",
                "reason": "The charity paid 4321 dollars for this.",
                "evidence": [],
            },
            event_id,
        )
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings, client=client)

    assert "4321" not in found.reason
    assert "signs the deduction off" in found.reason


def test_a_forbidden_approve_is_turned_into_ask_person(settings: Settings) -> None:
    """A donation of food somebody opened. No agent signs that off."""
    with session_scope() as session:
        event = _event(session)
        _record(session, event.id, label="opened milk carton", cost_basis_cents=300,
                fmv_mid=500)
        _option(session, event.id, models.OptionKind.trash, -2, rank=2)
        _option(
            session, event.id, models.OptionKind.donate, 200,
            needs_human_review=True, rank=1, kg_co2e=0.01,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        item_id = made[0].id
        event_id = event.id

    with session_scope() as session:
        client = ToolLoopClient(
            {"decision": "approve", "reason": "This one is fine.", "evidence": []},
            event_id,
        )
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings, client=client)

    assert found.decision == reviewer.DECISION_ASK
    assert found.downgraded_reason is not None
    assert "already opened" in found.downgraded_reason
    assert "A person has to decide this one" in found.reason


def test_an_estimate_far_above_the_catalog_cannot_be_approved(
    settings: Settings,
) -> None:
    with session_scope() as session:
        for index, cost in enumerate((1_000, 2_000, 3_000)):
            session.add(
                models.CatalogItem(
                    label=f"catalog item {index}",
                    item_class=models.ItemClass.untracked,
                    unit_cost_cents=cost,
                )
            )
        event = _event(session)
        _record(
            session,
            event.id,
            label="office chair",
            item_class=models.ItemClass.untracked,
            cost_basis_cents=0,
            fmv_mid=80_000,
        )
        session.commit()
        made = review.create_for_event(session, event.id, settings)
        session.commit()
        item_id = made[0].id
        event_id = event.id

    with session_scope() as session:
        client = ToolLoopClient(
            {"decision": "approve", "reason": "Looks right.", "evidence": []}, event_id
        )
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings, client=client)

    assert found.decision == reviewer.DECISION_ASK
    assert found.downgraded_reason is not None
    assert "catalog median" in found.downgraded_reason


def test_a_broken_model_still_leaves_a_proposal(settings: Settings) -> None:
    class Broken:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**_request: Any) -> Any:
                    raise RuntimeError("no network")

    item_id = _item(settings)
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        found = reviewer.propose(session, item, settings, client=Broken())

    assert found.reason
    assert found.steps


# The routes ----------------------------------------------------------------


def test_the_run_route_proposes_without_deciding(
    client: TestClient, settings: Settings
) -> None:
    _item(settings)
    body = client.post("/api/review/run", json={}).json()

    assert body["proposed"] == 1
    item = body["items"][0]
    assert item["status"] == "open"
    assert item["proposal"]["decision"] == "ask_person"
    assert item["proposal"]["steps"]
    assert item["agreed_with_agent"] is None


def test_running_twice_does_not_propose_twice(
    client: TestClient, settings: Settings
) -> None:
    _item(settings)
    client.post("/api/review/run", json={})
    again = client.post("/api/review/run", json={}).json()
    assert again["proposed"] == 0
    assert again["items"][0]["proposal"] is not None


def test_agreement_is_recorded_when_the_person_decides(
    client: TestClient, settings: Settings
) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        item.proposal_json = json.dumps(
            {"decision": "reject", "reason": "no", "evidence": [], "steps": []}
        )
        session.commit()

    body = client.post(f"/api/review/{item_id}/reject", json={"by": "nishad"}).json()
    assert body["agreed_with_agent"] is True
    assert body["item"]["agreed_with_agent"] is True


def test_disagreement_is_recorded_too(client: TestClient, settings: Settings) -> None:
    item_id = _item(settings)
    with session_scope() as session:
        item = session.get(models.ReviewItem, item_id)
        assert item is not None
        item.proposal_json = json.dumps(
            {"decision": "reject", "reason": "no", "evidence": [], "steps": []}
        )
        session.commit()

    body = client.post(f"/api/review/{item_id}/approve", json={"by": "nishad"}).json()
    assert body["agreed_with_agent"] is False


def test_ask_person_is_never_counted_as_agreement(
    client: TestClient, settings: Settings
) -> None:
    item_id = _item(settings)
    client.post("/api/review/run", json={})
    body = client.post(f"/api/review/{item_id}/approve", json={"by": "nishad"}).json()
    assert body["agreed_with_agent"] is None
