"""The six read-only tools the review agent may call, and nothing else.

PLAN.md 21a item 49. Every one of them reads the database and returns plain JSON.
None of them writes, posts, decides or reaches a model. The agent looks at a
ticket the way a person would: what was thrown away, what the estimator thought
it was worth, whether the register knows it, what the rule says, how the same
label was decided before, and what the policy thresholds are.

Every label and description on the way out goes through `as_data_label`, so a
string somebody typed into a form reaches the model as a quoted value and never
as a line of instruction.
"""

from __future__ import annotations

import json
import logging
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.agent.tools import as_data_label
from app.engine import rules

log = logging.getLogger(__name__)

GET_EVENT = "get_event"
GET_ESTIMATE = "get_estimate"
GET_REGISTER = "get_register"
GET_RULE = "get_rule"
FIND_SIMILAR = "find_similar"
GET_POLICY = "get_policy"

TOOL_NAMES: frozenset[str] = frozenset(
    {GET_EVENT, GET_ESTIMATE, GET_REGISTER, GET_RULE, FIND_SIMILAR, GET_POLICY}
)

MAX_ROWS = 10
DEFAULT_SIMILAR_DAYS = 90


class EventIdArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: int = Field(ge=1)


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(default="", max_length=80)


class RuleArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rule_id: str = Field(default="", max_length=40)


class SimilarArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", max_length=40)
    days: int = Field(default=DEFAULT_SIMILAR_DAYS, ge=1, le=3650)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": GET_EVENT,
            "description": (
                "One ticket in full: what it was identified as and how confidently, its "
                "class, mass and money, every option the engine scored, and every journal "
                "entry posted for it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The ticket id."}
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_ESTIMATE,
            "description": (
                "What the estimator said one ticket was worth: the low, mid and high "
                "ranges for value, repair, replacement and scrap, and where each came from."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "integer", "description": "The ticket id."}
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_REGISTER,
            "description": (
                "Rows on the fixed asset register matching a tag or a description, with "
                "cost, in service date, life, tax method and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A tag such as bb-0002, or part of a description.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_RULE,
            "description": (
                "One tax rule in plain language with its citation, by id. Call with no id "
                "to list every rule id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "A rule id such as ABANDON or DONATE_FOOD.",
                    }
                },
                "required": ["rule_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": FIND_SIMILAR,
            "description": (
                "Past tickets carrying the same label, and how their review items were "
                "decided, so a decision matches what was decided before."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "The item label."},
                    "days": {"type": "integer", "description": "How far back to look."},
                },
                "required": ["label", "days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_POLICY,
            "description": (
                "The thresholds this business runs on: the capitalization limit, the tax "
                "rate, how long a ticket may wait, and the catalog median value per class."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def get_event(session: Session, event_id: int) -> dict[str, Any]:
    """One ticket, whole. Every label on the way out is validated again."""
    event = session.get(models.Event, event_id)
    if event is None:
        return {"error": "no such ticket"}
    record = session.get(models.ItemRecord, event_id)
    options = list(
        session.scalars(
            select(models.OptionScore)
            .where(models.OptionScore.event_id == event_id)
            .order_by(models.OptionScore.id)
        )
    )
    identifications = list(
        session.scalars(
            select(models.Identification)
            .where(models.Identification.event_id == event_id)
            .order_by(models.Identification.id)
        )
    )
    entries = list(
        session.scalars(
            select(models.JournalEntry)
            .where(models.JournalEntry.event_id == event_id)
            .order_by(models.JournalEntry.id)
        )
    )
    return {
        "event_id": event.id,
        "created_at": event.created_at,
        "status": event.status.value,
        "mass_g": event.mass_g,
        "item": None
        if record is None
        else {
            "label": as_data_label(record.label),
            "class": record.item_class.value,
            "condition": record.condition,
            "flags": _loads(record.regulatory_flags_json, []),
            "cost_basis_cents": record.cost_basis_cents,
            "book_value_cents": record.book_value_cents,
            "tax_basis_cents": record.tax_basis_cents,
            "fmv_mid": record.fmv_mid,
            "fmv_source": record.fmv_source,
            "asset_id": record.asset_id,
        },
        "identifications": [
            {
                "method": row.method.value,
                "label": as_data_label(row.label),
                "confidence": row.confidence,
                "is_final": row.is_final,
                "provider": row.provider,
                "model": row.model,
            }
            for row in identifications
        ],
        "options": [
            {
                "option": row.option.value,
                "allowed": row.allowed,
                "blocked_reason": row.blocked_reason,
                "net_after_tax_cents": row.net_after_tax_cents,
                "kg_co2e": row.kg_co2e,
                "needs_human_review": row.needs_human_review,
                "rule_ids": _loads(row.rule_ids_json, []),
                "rank": row.rank,
            }
            for row in options
        ],
        "entries": [
            {"id": row.id, "memo": row.memo, "basis": row.basis.value} for row in entries
        ],
    }


def get_estimate(session: Session, event_id: int) -> dict[str, Any]:
    """The estimator's ranges for one ticket, and where each figure came from."""
    record = session.get(models.ItemRecord, event_id)
    if record is None:
        return {"error": "no item record for this ticket"}
    return {
        "event_id": event_id,
        "label": as_data_label(record.label),
        "value": {
            "low": record.fmv_low,
            "mid": record.fmv_mid,
            "high": record.fmv_high,
            "source": record.fmv_source,
        },
        "repair": {
            "low": record.repair_low,
            "mid": record.repair_mid,
            "high": record.repair_high,
            "source": record.repair_source,
        },
        "replacement": {
            "cents": record.replacement_cents,
            "source": record.replacement_source,
        },
        "scrap": {"cents": record.scrap_cents, "source": record.scrap_source},
    }


def get_register(session: Session, query: str) -> dict[str, Any]:
    """Register rows whose tag or description matches. At most ten come back."""
    needle = (query or "").strip().lower()
    rows = list(session.scalars(select(models.Asset).order_by(models.Asset.id)))
    if needle:
        rows = [
            row
            for row in rows
            if needle in row.tag.lower() or needle in row.description.lower()
        ]
    return {
        "query": needle,
        "count": len(rows),
        "rows": [
            {
                "id": row.id,
                "tag": row.tag,
                "description": as_data_label(row.description) or row.description[:40],
                "cost_cents": row.cost_cents,
                "in_service_date": row.in_service_date,
                "book_life_months": row.book_life_months,
                "tax_method": row.tax_method.value,
                "status": row.status.value,
            }
            for row in rows[:MAX_ROWS]
        ],
    }


def get_rule(rule_id: str) -> dict[str, Any]:
    """One rule from `tax_rules.yaml`, or the list of ids when none was named."""
    wanted = (rule_id or "").strip()
    if not wanted:
        return {"rule_ids": [rule.id for rule in rules.all_rules()]}
    try:
        rule = rules.get(wanted)
    except rules.UnknownRule:
        return {
            "error": "no such rule",
            "rule_ids": [rule.id for rule in rules.all_rules()],
        }
    return {
        "id": rule.id,
        "title": rule.title,
        "plain_text": rule.plain_text,
        "citation_url": rule.citation_url,
        "needs_human_review": rule.needs_human_review,
    }


def find_similar(session: Session, label: str, days: int) -> dict[str, Any]:
    """Past tickets with this label, and how their review items were decided."""
    needle = (label or "").strip().lower()
    if not needle:
        return {"error": "a label is needed"}
    since = datetime.now(UTC) - timedelta(days=days)

    records = list(
        session.scalars(select(models.ItemRecord).where(models.ItemRecord.label == needle))
    )
    ids = [row.event_id for row in records]
    if not ids:
        return {"label": needle, "days": days, "count": 0, "rows": []}

    events = {
        row.id: row
        for row in session.scalars(select(models.Event).where(models.Event.id.in_(ids)))
    }
    decisions: dict[int, models.ReviewItem] = {}
    for row in session.scalars(
        select(models.ReviewItem).where(models.ReviewItem.event_id.in_(ids))
    ):
        decisions[row.event_id] = row

    rows: list[dict[str, Any]] = []
    for record in records:
        event = events.get(record.event_id)
        if event is None:
            continue
        try:
            when = datetime.fromisoformat(event.created_at)
        except ValueError:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=UTC)
        if when < since:
            continue
        decided = decisions.get(record.event_id)
        rows.append(
            {
                "event_id": record.event_id,
                "created_at": event.created_at,
                "status": event.status.value,
                "cost_basis_cents": record.cost_basis_cents,
                "fmv_mid": record.fmv_mid,
                "review_kind": decided.kind.value if decided else None,
                "review_status": decided.status.value if decided else None,
                "decided_by": decided.decided_by if decided else None,
            }
        )
    rows.sort(key=lambda row: str(row["created_at"]), reverse=True)
    return {"label": needle, "days": days, "count": len(rows), "rows": rows[:MAX_ROWS]}


def catalog_medians(session: Session) -> dict[str, int]:
    """The middle value the catalog carries for each class, in cents.

    The agent is not allowed to approve an estimate far above this. It is computed
    here rather than guessed, and an empty catalog gives no median at all rather
    than a zero that would make every estimate look enormous.
    """
    by_class: dict[str, list[int]] = {}
    for row in session.scalars(select(models.CatalogItem)):
        value = row.unit_cost_cents
        if value is None or value <= 0:
            continue
        by_class.setdefault(row.item_class.value, []).append(value)
    return {
        name: int(statistics.median(values)) for name, values in by_class.items() if values
    }


def get_policy(session: Session, settings: Any) -> dict[str, Any]:
    """The thresholds this business runs on."""
    from app.ledger.review import review_after_s

    return {
        "capitalization_threshold_cents": int(
            getattr(settings, "capitalization_threshold_cents", 50_000)
        ),
        "tax_rate": float(getattr(settings, "tax_rate", 0.21)),
        "confident_p": float(getattr(settings, "confident_p", 0.8)),
        "review_after_s": review_after_s(settings),
        "catalog_median_cents_by_class": catalog_medians(session),
    }


def run_tool(
    session: Session, settings: Any, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch one call. An unknown name or a bad argument is an answer, not a crash."""
    if name not in TOOL_NAMES:
        log.warning("the review agent asked for a tool that does not exist: %s", name)
        return {"error": "no such tool", "tools": sorted(TOOL_NAMES)}
    try:
        if name == GET_POLICY:
            NoArgs.model_validate(arguments)
            return get_policy(session, settings)
        if name == GET_EVENT:
            return get_event(session, EventIdArgs.model_validate(arguments).event_id)
        if name == GET_ESTIMATE:
            return get_estimate(session, EventIdArgs.model_validate(arguments).event_id)
        if name == GET_REGISTER:
            return get_register(session, QueryArgs.model_validate(arguments).query)
        if name == GET_RULE:
            return get_rule(RuleArgs.model_validate(arguments).rule_id)
        similar = SimilarArgs.model_validate(arguments)
    except ValidationError:
        log.warning("the review agent called %s with arguments this code cannot read", name)
        return {"error": "the arguments for this tool were not readable"}
    return find_similar(session, similar.label, similar.days)


def summarise_args(arguments: dict[str, Any]) -> str:
    """What the step list shows for one call. Short, and safe to draw."""
    if not arguments:
        return ""
    parts = [f"{key}={str(value)[:40]}" for key, value in sorted(arguments.items())]
    return ", ".join(parts)[:120]
