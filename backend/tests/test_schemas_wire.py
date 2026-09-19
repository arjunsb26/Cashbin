"""Every wire example in PLAN.md section 6 round-trips through the schemas."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    LCD_BIG_MAX,
    LCD_LINE_MAX,
    BackendToBin,
    BackendToPhone,
    BinToBackend,
    PhoneToBackend,
    ScreenResult,
    UiMessage,
)

BIN_TO_BACKEND: list[dict[str, Any]] = [
    {"type": "hello", "fw": "0.1", "device": "bin-1"},
    {"type": "weight", "t": 123456, "g": 412.3},
    {"type": "pong", "t": 123999},
    {"type": "button", "id": "a"},
]

BACKEND_TO_BIN: list[dict[str, Any]] = [
    {"type": "ping"},
    {"type": "tare"},
    {"type": "screen", "s": "idle"},
    {"type": "screen", "s": "thinking"},
    {
        "type": "screen",
        "s": "result",
        "l1": "Keyboard",
        "big": "-$20",
        "l2": "Removed from register",
        "c": "amber",
    },
    {"type": "screen", "s": "ask", "l1": "Not sure", "l2": "Check the dashboard"},
    {"type": "screen", "s": "offline"},
]

PHONE_TO_BACKEND: list[dict[str, Any]] = [
    {"type": "hello", "ua": "Mozilla/5.0 (iPhone)"},
    {"type": "pong"},
]

BACKEND_TO_PHONE: list[dict[str, Any]] = [
    {
        "type": "result",
        "event_id": 17,
        "title": "Keyboard",
        "big": "-$20",
        "line": "Removed from register",
        "tone": "amber",
        "best_option": "recycle",
    },
    {
        "type": "ask",
        "event_id": 18,
        "candidates": [{"label": "wrap", "p": 0.41}, {"label": "burrito", "p": 0.37}],
    },
    {"type": "idle"},
]

bin_in: TypeAdapter[Any] = TypeAdapter(BinToBackend)
bin_out: TypeAdapter[Any] = TypeAdapter(BackendToBin)
phone_in: TypeAdapter[Any] = TypeAdapter(PhoneToBackend)
phone_out: TypeAdapter[Any] = TypeAdapter(BackendToPhone)
ui_out: TypeAdapter[Any] = TypeAdapter(UiMessage)


@pytest.mark.parametrize("payload", BIN_TO_BACKEND, ids=[p["type"] for p in BIN_TO_BACKEND])
def test_bin_to_backend_round_trips(payload: dict[str, Any]) -> None:
    model = bin_in.validate_python(payload)
    assert json.loads(model.model_dump_json()) == payload


@pytest.mark.parametrize(
    "payload", BACKEND_TO_BIN, ids=[f"{p['type']}-{p.get('s', '')}" for p in BACKEND_TO_BIN]
)
def test_backend_to_bin_round_trips(payload: dict[str, Any]) -> None:
    """Every field survives, except that an over-wide LCD line comes back cut to 20."""
    model = bin_out.validate_python(payload)
    dumped = json.loads(model.model_dump_json())
    assert dumped.keys() == payload.keys()
    for key, value in payload.items():
        if key in {"l1", "l2"}:
            assert dumped[key] == str(value)[:LCD_LINE_MAX]
        elif key == "big":
            assert dumped[key] == str(value)[:LCD_BIG_MAX]
        else:
            assert dumped[key] == value


@pytest.mark.parametrize("payload", PHONE_TO_BACKEND, ids=[p["type"] for p in PHONE_TO_BACKEND])
def test_phone_to_backend_round_trips(payload: dict[str, Any]) -> None:
    model = phone_in.validate_python(payload)
    assert json.loads(model.model_dump_json())["type"] == payload["type"]


@pytest.mark.parametrize("payload", BACKEND_TO_PHONE, ids=[p["type"] for p in BACKEND_TO_PHONE])
def test_backend_to_phone_round_trips(payload: dict[str, Any]) -> None:
    model = phone_out.validate_python(payload)
    dumped = json.loads(model.model_dump_json())
    for key, value in payload.items():
        assert dumped[key] == value


def test_unknown_fields_are_ignored() -> None:
    """PLAN.md section 6. A firmware that sends more than we asked for still works."""
    model = bin_in.validate_python(
        {"type": "weight", "t": 1, "g": 2.5, "temperature_c": 31.0, "seq": 9}
    )
    assert json.loads(model.model_dump_json()) == {"type": "weight", "t": 1, "g": 2.5}


def test_unknown_type_is_refused() -> None:
    with pytest.raises(ValidationError):
        bin_in.validate_python({"type": "explode", "g": 1.0})


def test_lcd_line_limit_is_enforced() -> None:
    """The backend truncates, so the firmware never receives more than it can draw."""
    screen = ScreenResult(l1="x" * (LCD_LINE_MAX + 5), big="-$20", l2="ok", c="amber")
    assert screen.l1 == "x" * LCD_LINE_MAX


def test_lcd_big_limit_is_enforced() -> None:
    screen = ScreenResult(l1="ok", big="x" * (LCD_BIG_MAX + 5), l2="ok", c="amber")
    assert screen.big == "x" * LCD_BIG_MAX


def test_lcd_colour_enum_is_closed() -> None:
    with pytest.raises(ValidationError):
        ScreenResult(l1="ok", big="-$20", l2="ok", c="purple")


UI_EXAMPLES: list[dict[str, Any]] = [
    {"type": "weight", "t": 12.5, "g": 2412.0},
    {
        "type": "event.created",
        "event": {"id": 1, "created_at": "2026-09-19T20:00:00+00:00", "kind": "toss",
                  "status": "detected", "mass_g": 212.0, "mass_err_g": 2.0},
    },
    {
        "type": "event.updated",
        "event": {"id": 1, "created_at": "2026-09-19T20:00:00+00:00", "kind": "toss",
                  "status": "posted", "label": "keyboard", "class": "fixed_asset"},
    },
    {
        "type": "journal.posted",
        "entry": {"id": 4, "event_id": 1, "posted_at": "2026-09-19T20:00:01+00:00",
                  "memo": "Keyboard disposal", "basis": "book",
                  "lines": [{"id": 1, "entry_id": 4, "account": "1590", "debit_cents": 10000},
                            {"id": 2, "entry_id": 4, "account": "1500", "credit_cents": 10000}]},
    },
    {
        "type": "ask.opened",
        "event_id": 18,
        "candidates": [{"label": "wrap", "p": 0.41}, {"label": "burrito", "p": 0.37}],
    },
    {"type": "ask.resolved", "event_id": 18, "label": "burrito", "by": "person"},
    {
        "type": "metrics.updated",
        "summary": {"saved_if_followed_cents": 4180, "kg_diverted": 3.2, "events": 27,
                    "first_try_accuracy": 0.89},
    },
    {"type": "device.status", "device": "bin", "connected": True},
]


@pytest.mark.parametrize("payload", UI_EXAMPLES, ids=[p["type"] for p in UI_EXAMPLES])
def test_ui_topics_round_trip(payload: dict[str, Any]) -> None:
    model = ui_out.validate_python(payload)
    assert json.loads(model.model_dump_json(by_alias=True))["type"] == payload["type"]


def test_every_ui_topic_has_a_message() -> None:
    """The topic list in PLAN.md section 6 and the union in schemas.py must not drift."""
    topics = {p["type"] for p in UI_EXAMPLES}
    assert topics == {
        "weight",
        "event.created",
        "event.updated",
        "journal.posted",
        "ask.opened",
        "ask.resolved",
        "metrics.updated",
        "device.status",
    }
