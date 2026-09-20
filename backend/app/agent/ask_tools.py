"""The eight read-only tools the ask agent may call, and nothing else.

A judge types a question about the books. The agent cannot answer it from the
question alone, so it looks things up: the journal, the trial balance, the
register, the range totals, recent tickets, the last close, the tax rules and
the thresholds this business runs on.

Every one of them is a plain function over the session that returns JSON this
code built. None of them writes, posts, decides or reaches a model. Every label
and description on the way out goes through `as_data_label`, so a string
somebody typed into a form reaches the model as a quoted value and never as a
line of instruction.

Figures come back in cents, because `prose.grounded` checks the answer against
these results and a figure that was never returned cannot be quoted.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.agent.tools import as_data_label
from app.engine import rules as engine_rules

log = logging.getLogger(__name__)

JOURNAL_ENTRIES = "journal_entries"
TRIAL_BALANCE = "trial_balance"
REGISTER = "register"
STATS = "stats"
RECENT_TICKETS = "recent_tickets"
CLOSE_LATEST = "close_latest"
RULES = "rules"
POLICY = "policy"

TOOL_NAMES: frozenset[str] = frozenset(
    {
        JOURNAL_ENTRIES,
        TRIAL_BALANCE,
        REGISTER,
        STATS,
        RECENT_TICKETS,
        CLOSE_LATEST,
        RULES,
        POLICY,
    }
)

MAX_ROWS = 20
MAX_BUCKETS = 31
DEFAULT_DAYS = 14
MAX_DAYS = 365
QUERY_MAX = 40


class DaysAccountArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    days: int = Field(default=DEFAULT_DAYS, ge=1, le=MAX_DAYS)
    account: str = Field(default="", max_length=QUERY_MAX)


class BasisArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    basis: str = Field(default="book", max_length=16)


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str = Field(default="", max_length=QUERY_MAX)


class StatsArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bucket: str = Field(default="day", max_length=8)
    days: int = Field(default=DEFAULT_DAYS, ge=1, le=MAX_DAYS)


class RecentArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    days: int = Field(default=DEFAULT_DAYS, ge=1, le=MAX_DAYS)
    label: str = Field(default="", max_length=QUERY_MAX)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": JOURNAL_ENTRIES,
            "description": (
                "Journal entries posted in the last few days, newest first, each with its "
                "memo, its basis and its debit and credit lines in cents. Narrow it to one "
                "account by code or by name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How far back to look."},
                    "account": {
                        "type": "string",
                        "description": "An account code such as 5100, or part of its name.",
                    },
                },
                "required": ["days", "account"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": TRIAL_BALANCE,
            "description": (
                "Debits and credits per account in cents, and whether the two columns "
                "agree. Basis is book for the real ledger or tax_memo for the tax side."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "basis": {
                        "type": "string",
                        "description": "book or tax_memo.",
                    }
                },
                "required": ["basis"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": REGISTER,
            "description": (
                "Rows on the fixed asset register matching a tag or a description, with "
                "cost, in service date, life, tax method, status, today's book value and "
                "today's tax basis. Call with an empty query for the whole register."
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
            "name": STATS,
            "description": (
                "What the bin recorded over a range of days, by day or by week, with the "
                "totals split by category: food, packaging, equipment, e-waste and other."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bucket": {"type": "string", "description": "day or week."},
                    "days": {"type": "integer", "description": "How many days the range covers."},
                },
                "required": ["bucket", "days"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": RECENT_TICKETS,
            "description": (
                "Recent tickets, newest first, each with what it was called, its class, the "
                "sentence the bin said about it, the best option the engine allowed, the "
                "money on it in cents and the carbon it avoided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How far back to look."},
                    "label": {
                        "type": "string",
                        "description": "Only tickets whose label contains this text.",
                    },
                },
                "required": ["days", "label"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": CLOSE_LATEST,
            "description": (
                "The most recent period close: its range, its totals and every self check "
                "it ran with the result of each."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": RULES,
            "description": (
                "Every tax rule the engine can cite, in plain language, with its citation "
                "and whether it needs a person to sign it off."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": POLICY,
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


def _today() -> date:
    return datetime.now(UTC).date()


def _event_date(row: models.Event) -> date:
    try:
        parsed = datetime.fromisoformat(row.created_at)
    except ValueError:
        return _today()
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).date()


# The eight tools -----------------------------------------------------------


def journal_entries(session: Session, days: int, account: str) -> dict[str, Any]:
    """Entries posted inside the range, newest first, at most twenty."""
    from app.ledger import queries

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    needle = (account or "").strip().lower()

    rows = [row for row in queries.list_entries(session) if (row.posted_at or "") >= since]
    if needle:
        rows = [
            row
            for row in rows
            if any(
                needle in line.account.lower() or needle in (line.account_name or "").lower()
                for line in row.lines
            )
        ]
    rows.reverse()

    debit_total = sum(line.debit_cents for row in rows for line in row.lines)
    credit_total = sum(line.credit_cents for row in rows for line in row.lines)
    return {
        "days": days,
        "account": needle,
        "count": len(rows),
        "total_debit_cents": debit_total,
        "total_credit_cents": credit_total,
        "entries": [
            {
                "id": row.id,
                "event_id": row.event_id,
                "posted_at": row.posted_at,
                "memo": row.memo,
                "basis": row.basis.value,
                "lines": [
                    {
                        "account": line.account,
                        "account_name": line.account_name,
                        "debit_cents": line.debit_cents,
                        "credit_cents": line.credit_cents,
                    }
                    for line in row.lines
                ],
            }
            for row in rows[:MAX_ROWS]
        ],
    }


def trial_balance(session: Session, basis: str) -> dict[str, Any]:
    """Debits and credits per account, and whether the two columns agree."""
    from app.ledger import queries

    wanted = (basis or "book").strip().lower()
    try:
        which = models.JournalBasis(wanted)
    except ValueError:
        return {
            "error": "basis must be book or tax_memo",
            "bases": [row.value for row in models.JournalBasis],
        }
    rows = queries.trial_balance(session, which)
    return {
        "basis": which.value,
        "count": len(rows),
        "total_debit_cents": sum(row.debit_cents for row in rows),
        "total_credit_cents": sum(row.credit_cents for row in rows),
        "balanced": queries.is_balanced(rows),
        "rows": [
            {
                "account": row.account,
                "account_name": row.account_name,
                "debit_cents": row.debit_cents,
                "credit_cents": row.credit_cents,
            }
            for row in rows
        ],
    }


def register(session: Session, query: str) -> dict[str, Any]:
    """Register rows with today's book value and tax basis. At most twenty come back."""
    from app.api.assets import to_asset_info
    from app.engine import depreciation

    needle = (query or "").strip().lower()
    rows = list(session.scalars(select(models.Asset).order_by(models.Asset.id)))
    if needle:
        rows = [
            row
            for row in rows
            if needle in row.tag.lower() or needle in row.description.lower()
        ]

    on = _today()
    listed: list[dict[str, Any]] = []
    for row in rows[:MAX_ROWS]:
        info = to_asset_info(row)
        gone = row.status is models.AssetStatus.disposed
        listed.append(
            {
                "id": row.id,
                "tag": row.tag,
                "description": as_data_label(row.description) or row.description[:40],
                "category": row.category,
                "cost_cents": row.cost_cents,
                "in_service_date": row.in_service_date,
                "book_life_months": row.book_life_months,
                "tax_method": row.tax_method.value,
                "status": row.status.value,
                "book_value_cents": (
                    0 if gone else depreciation.book_value(info, on).book_value_cents
                ),
                "tax_basis_cents": 0 if gone else depreciation.tax_basis(info, on),
                "disposed_event_id": row.disposed_event_id,
            }
        )
    return {
        "query": needle,
        "count": len(rows),
        "returned": len(listed),
        "total_cost_cents": sum(row.cost_cents for row in rows),
        "rows": listed,
    }


def stats(session: Session, bucket: str, days: int) -> dict[str, Any]:
    """The same arithmetic `/api/stats` serves, with the categories behind it."""
    from app.ledger import stats as stats_module

    which = bucket if bucket in {stats_module.BUCKET_DAY, stats_module.BUCKET_WEEK} else "day"
    end = _today()
    start = end - timedelta(days=days - 1)

    loaded = stats_module.load(session, start, end)
    buckets = stats_module.fill_buckets(loaded, start, end, which)
    averages = stats_module.averages(buckets, start, end)

    by_category: dict[str, dict[str, float]] = {}
    for holder in buckets:
        for name, values in holder.by_category.items():
            into = by_category.setdefault(name, {"tosses": 0.0, "cents": 0.0, "kg": 0.0})
            for key, value in values.items():
                into[key] += value

    categories = [
        {
            "category": name,
            "tosses": int(values["tosses"]),
            "cents": int(values["cents"]),
            "kg": round(values["kg"], 3),
        }
        for name, values in by_category.items()
        if values["tosses"]
    ]
    categories.sort(key=lambda row: (-int(str(row["cents"])), str(row["category"])))

    return {
        "bucket": which,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "totals": {
            "tosses": sum(row.tosses for row in buckets),
            "wasted_cents": sum(row.wasted_cents for row in buckets),
            "book_loss_cents": sum(row.book_loss_cents for row in buckets),
            "estimated_value_cents": sum(row.estimated_value_cents for row in buckets),
            "kg_landfill": round(sum(row.kg_landfill for row in buckets), 3),
            "kg_co2e_avoided": round(sum(row.kg_co2e_avoided for row in buckets), 3),
            "asks": sum(row.asks for row in buckets),
        },
        "averages_per_day": averages,
        "by_category": categories,
        "buckets": [row.as_dict() for row in buckets[-MAX_BUCKETS:]],
        "findings": stats_module.suggestions(loaded, buckets),
    }


def recent_tickets(session: Session, days: int, label: str) -> dict[str, Any]:
    """Recent tosses with what each one meant, newest first, at most twenty."""
    from app.engine import carbon
    from app.pipeline import sentence_for_row

    needle = (label or "").strip().lower()
    since = _today() - timedelta(days=days - 1)

    events = [
        row
        for row in session.scalars(select(models.Event).order_by(models.Event.id.desc()))
        if row.kind is models.EventKind.toss and _event_date(row) >= since
    ]
    ids = [row.id for row in events]

    records: dict[int, models.ItemRecord] = {}
    options: dict[int, list[models.OptionScore]] = {}
    if ids:
        for record in session.scalars(
            select(models.ItemRecord).where(models.ItemRecord.event_id.in_(ids))
        ):
            records[record.event_id] = record
        for score in session.scalars(
            select(models.OptionScore)
            .where(models.OptionScore.event_id.in_(ids))
            .order_by(models.OptionScore.id)
        ):
            options.setdefault(score.event_id, []).append(score)

    listed: list[dict[str, Any]] = []
    for event in events:
        found = records.get(event.id)
        if needle and not (found is not None and needle in found.label.lower()):
            continue
        scores = options.get(event.id, [])
        best = _best(scores)
        trash = next((row for row in scores if row.option is models.OptionKind.trash), None)
        avoided = (
            carbon.avoided_co2e(trash.kg_co2e, best.kg_co2e)
            if trash is not None and best is not None
            else None
        )
        listed.append(
            {
                "event_id": event.id,
                "created_at": event.created_at,
                "status": event.status.value,
                "mass_g": round(event.mass_g, 1) if event.mass_g is not None else None,
                "label": as_data_label(found.label) if found is not None else None,
                "class": found.item_class.value if found is not None else None,
                "headline": sentence_for_row(found, scores) if found is not None else "",
                "cents": _ticket_cents(found),
                "best_option": best.option.value if best is not None else None,
                "saved_if_followed_cents": (
                    best.net_after_tax_cents - trash.net_after_tax_cents
                    if best is not None and trash is not None
                    else None
                ),
                "kg_co2e": round(best.kg_co2e, 3) if best is not None and best.kg_co2e else None,
                "kg_co2e_avoided": round(avoided, 3) if avoided else None,
            }
        )
        if len(listed) >= MAX_ROWS:
            break

    return {
        "days": days,
        "label": needle,
        "count": len(listed),
        "tickets": listed,
    }


def _ticket_cents(record: models.ItemRecord | None) -> int:
    """The one figure the ticket leads with, off the stored row.

    The same choice `pipeline.headline_cents` makes: a register asset leads with the book
    loss, inventory with the waste written off, and anything else with what it was worth.
    Both come back positive here, because the sentence beside them says which it is.
    """
    if record is None:
        return 0
    if record.item_class is models.ItemClass.fixed_asset:
        return record.book_value_cents or 0
    if record.item_class is models.ItemClass.inventory:
        return record.cost_basis_cents or 0
    return record.fmv_mid or 0


def _best(scores: list[models.OptionScore]) -> models.OptionScore | None:
    allowed = [row for row in scores if row.allowed]
    if not allowed:
        return None
    ranked = [row for row in allowed if row.rank == 1]
    return ranked[0] if ranked else max(allowed, key=lambda row: row.net_after_tax_cents)


def close_latest(session: Session) -> dict[str, Any]:
    """The last close that was run, with its schedules trimmed to their totals."""
    row = session.scalars(
        select(models.Close).order_by(models.Close.id.desc()).limit(1)
    ).first()
    if row is None:
        return {"error": "no close has been run yet"}
    checks = _loads(row.checks_json, [])
    return {
        "id": row.id,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "created_at": row.created_at,
        "status": row.status,
        "totals": _trim(_loads(row.totals_json, {})),
        "checks": [
            {
                "title": check.get("title"),
                "result": check.get("result"),
                "detail": check.get("detail"),
            }
            for check in checks
            if isinstance(check, dict)
        ]
        if isinstance(checks, list)
        else [],
    }


def _trim(node: Any) -> Any:
    """A close's totals with the long schedules cut to their count and their total.

    The rollforward, the reconciliation and Form 4797 each carry a row per asset. The
    figures worth quoting are the totals under them, and a reply carrying eighty rows
    costs the agent its whole budget on one lookup.
    """
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "rows" and isinstance(value, list):
            out["row_count"] = len(value)
            continue
        out[key] = _trim(value) if isinstance(value, dict) else value
    return out


def rules() -> dict[str, Any]:
    """Every rule the engine can cite, the same words `/api/rules` serves."""
    return {
        "count": len(engine_rules.all_rules()),
        "rules": [
            {
                "id": rule.id,
                "title": rule.title,
                "plain_text": rule.plain_text,
                "citation_url": rule.citation_url,
                "needs_human_review": rule.needs_human_review,
            }
            for rule in engine_rules.all_rules()
        ],
    }


def policy(session: Session, settings: Any) -> dict[str, Any]:
    """The thresholds this business runs on. The review agent reads the same ones."""
    from app.agent import review_tools

    return review_tools.get_policy(session, settings)


def run_tool(
    session: Session, settings: Any, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch one call. An unknown name or a bad argument is an answer, not a crash."""
    if name not in TOOL_NAMES:
        log.warning("the ask agent asked for a tool that does not exist: %s", name)
        return {"error": "no such tool", "tools": sorted(TOOL_NAMES)}
    try:
        if name == JOURNAL_ENTRIES:
            journal_args = DaysAccountArgs.model_validate(arguments)
            return journal_entries(session, journal_args.days, journal_args.account)
        if name == TRIAL_BALANCE:
            return trial_balance(session, BasisArgs.model_validate(arguments).basis)
        if name == REGISTER:
            return register(session, QueryArgs.model_validate(arguments).query)
        if name == STATS:
            stats_args = StatsArgs.model_validate(arguments)
            return stats(session, stats_args.bucket, stats_args.days)
        if name == RECENT_TICKETS:
            recent_args = RecentArgs.model_validate(arguments)
            return recent_tickets(session, recent_args.days, recent_args.label)
        NoArgs.model_validate(arguments)
    except ValidationError:
        log.warning("the ask agent called %s with arguments this code cannot read", name)
        return {"error": "the arguments for this tool were not readable"}
    if name == CLOSE_LATEST:
        return close_latest(session)
    if name == RULES:
        return rules()
    return policy(session, settings)


def summarise_args(arguments: dict[str, Any]) -> str:
    """What the step list shows for one call. Short, and safe to draw."""
    if not arguments:
        return ""
    parts = [f"{key}={str(value)[:40]}" for key, value in sorted(arguments.items())]
    return ", ".join(parts)[:120]
