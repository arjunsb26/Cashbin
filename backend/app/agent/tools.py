"""The four read-only tools the investigator may call.

Every tool is a plain function over the database that returns JSON this code
built. Nothing a person typed is ever put into the instruction text: labels are
already `ValidatedLabel`s, and they travel inside a JSON data value under a key
the code chose. A tool can read; no tool can write, and none of them touches a
number that the close already computed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ledger.close import PeriodRows

log = logging.getLogger(__name__)

MAX_EVENTS = 60
MAX_TRACE_POINTS = 120
MAX_IDENTIFICATIONS = 20

GET_EVENTS = "get_events"
GET_TRACE = "get_trace"
GET_BAG_CHANGES = "get_bag_changes"
GET_IDENTIFICATIONS = "get_identifications"

TOOL_NAMES: tuple[str, ...] = (GET_EVENTS, GET_TRACE, GET_BAG_CHANGES, GET_IDENTIFICATIONS)


class EventIdArgs(BaseModel):
    """The one argument the per-event tools take."""

    model_config = ConfigDict(extra="ignore")

    event_id: int = Field(ge=1)


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": GET_EVENTS,
            "description": (
                "Every ticket in the period being closed, with its mass, its measurement "
                "error, its status and whether it has a weight trace and an item record."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_TRACE,
            "description": (
                "The weight trace around one ticket as time in seconds and grams, with the "
                "baseline before and after the step."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ticket id, from get_events.",
                    }
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_BAG_CHANGES,
            "description": (
                "Every bag change and removal in the period, with how many grams left the "
                "bin and when."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": GET_IDENTIFICATIONS,
            "description": (
                "What the system decided one ticket was: every identification attempt, the "
                "method, the confidence, the provider and model, and which one is final."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ticket id, from get_events.",
                    }
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _trace_points(raw: str | None) -> list[tuple[float, float]]:
    """`[[t_seconds, grams], ...]` as numbers, dropping anything that is not a pair."""
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    points: list[tuple[float, float]] = []
    for point in loaded:
        if isinstance(point, list | tuple) and len(point) >= 2:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
    return points


def get_events(rows: PeriodRows) -> dict[str, Any]:
    """Every ticket in the period, oldest first, capped so the reply stays small."""
    listed: list[dict[str, Any]] = []
    for event in rows.events[:MAX_EVENTS]:
        record = rows.item_records.get(event.id)
        listed.append(
            {
                "event_id": event.id,
                "created_at": event.created_at,
                "kind": event.kind.value,
                "mass_g": round(event.mass_g, 3) if event.mass_g is not None else None,
                "mass_err_g": (
                    round(event.mass_err_g, 3) if event.mass_err_g is not None else None
                ),
                "status": event.status.value,
                "label": record.label if record else None,
                "class": record.item_class.value if record else None,
                "has_trace": bool(event.trace_json),
                "has_item_record": record is not None,
                "has_photo": bool(event.frame_after or event.crop),
            }
        )
    return {
        "period": {"start": rows.period_start, "end": rows.period_end},
        "count": len(rows.events),
        "returned": len(listed),
        "events": listed,
    }


def get_trace(rows: PeriodRows, event_id: int) -> dict[str, Any]:
    """The weight trace around one ticket, thinned to a readable number of points."""
    event = next((row for row in rows.events if row.id == event_id), None)
    if event is None:
        return {"event_id": event_id, "found": False, "reason": "no ticket with that id"}
    points = _trace_points(event.trace_json)
    step = max(1, len(points) // MAX_TRACE_POINTS)
    thinned = [[round(t, 3), round(g, 3)] for t, g in points[::step]]
    grams = [g for _t, g in points]
    return {
        "event_id": event_id,
        "found": True,
        "kind": event.kind.value,
        "mass_g": round(event.mass_g, 3) if event.mass_g is not None else None,
        "mass_err_g": round(event.mass_err_g, 3) if event.mass_err_g is not None else None,
        "points": thinned,
        "point_count": len(points),
        "first_g": round(grams[0], 3) if grams else None,
        "last_g": round(grams[-1], 3) if grams else None,
    }


def get_bag_changes(rows: PeriodRows) -> dict[str, Any]:
    """Bag changes and removals: the mass that left the bin without a ticket."""
    events = sorted(rows.bag_changes + rows.removals, key=lambda event: event.id)
    total = 0.0
    listed: list[dict[str, Any]] = []
    for event in events:
        removed = -(event.mass_g or 0.0)
        total += removed
        listed.append(
            {
                "event_id": event.id,
                "created_at": event.created_at,
                "kind": event.kind.value,
                "mass_g": round(event.mass_g, 3) if event.mass_g is not None else None,
                "removed_g": round(removed, 3),
            }
        )
    return {
        "count": len(listed),
        "removed_g_total": round(total, 3),
        "changes": listed,
    }


def get_identifications(rows: PeriodRows, event_id: int) -> dict[str, Any]:
    """Every identification attempt on one ticket, in the order they were made."""
    if not any(row.id == event_id for row in rows.events):
        return {"event_id": event_id, "found": False, "reason": "no ticket with that id"}
    listed = [
        {
            "method": ident.method.value,
            "label": ident.label,
            "class": ident.item_class.value if ident.item_class else None,
            "confidence": ident.confidence,
            "provider": ident.provider,
            "model": ident.model,
            "latency_ms": ident.latency_ms,
            "is_final": ident.is_final,
        }
        for ident in rows.identifications.get(event_id, [])[:MAX_IDENTIFICATIONS]
    ]
    return {"event_id": event_id, "found": True, "count": len(listed), "identifications": listed}


def run_tool(rows: PeriodRows, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one tool call. An unknown name or a bad argument is an answer, not a crash."""
    if name not in TOOL_NAMES:
        log.warning("the investigator asked for a tool that does not exist: %s", name)
        return {"error": "no such tool", "tools": list(TOOL_NAMES)}
    try:
        if name == GET_EVENTS:
            NoArgs.model_validate(arguments)
            return get_events(rows)
        if name == GET_BAG_CHANGES:
            NoArgs.model_validate(arguments)
            return get_bag_changes(rows)
        args = EventIdArgs.model_validate(arguments)
    except ValidationError:
        log.warning("the investigator called %s with arguments this code cannot read", name)
        return {"error": "event_id must be a positive whole number"}
    if name == GET_TRACE:
        return get_trace(rows, args.event_id)
    return get_identifications(rows, args.event_id)


def period_event_ids(rows: PeriodRows) -> set[int]:
    """The ids that exist in this period. A note may not name anything else."""
    return {event.id for event in rows.events}
