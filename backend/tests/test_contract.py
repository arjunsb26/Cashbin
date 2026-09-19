"""firmware_contract.md must keep validating against the protocol models.

CLAUDE.md: the document and the models change in the same commit. This test reads every fenced
JSON block in the file, one object per line, and validates each one. When the doc drifts, the
suite goes red and whoever changed one side has to change the other.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BackendToBin, BinToBackend

CONTRACT_FILE = Path(__file__).resolve().parent.parent.parent / "firmware_contract.md"

# Which heading a block sits under decides which direction it belongs to.
_ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "Bin to backend (`/ws/bin`)": TypeAdapter(BinToBackend),
    "Backend to bin": TypeAdapter(BackendToBin),
}

_HEADING = re.compile(r"^##\s+(.*?)\s*$")
_FENCE = re.compile(r"^```(\w*)\s*$")


def contract_lines() -> list[tuple[str, int, str]]:
    """Every JSON line in the document as (section heading, line number, text)."""
    found: list[tuple[str, int, str]] = []
    section = ""
    fence_lang: str | None = None
    for number, raw in enumerate(CONTRACT_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        fence = _FENCE.match(raw)
        if fence:
            fence_lang = None if fence_lang is not None else (fence.group(1) or "")
            continue
        if fence_lang is None:
            heading = _HEADING.match(raw)
            if heading:
                section = heading.group(1)
            continue
        if fence_lang == "json" and raw.strip():
            found.append((section, number, raw.strip()))
    return found


CONTRACT_LINES = contract_lines()


def test_the_document_is_present_and_has_both_directions() -> None:
    sections = {section for section, _, _ in CONTRACT_LINES}
    assert sections == set(_ADAPTERS), f"unexpected sections in the contract: {sections}"


def test_every_direction_has_examples() -> None:
    counts = dict.fromkeys(_ADAPTERS, 0)
    for section, _, _ in CONTRACT_LINES:
        counts[section] += 1
    assert counts["Bin to backend (`/ws/bin`)"] == 4
    assert counts["Backend to bin"] == 7


@pytest.mark.parametrize(
    ("section", "line_no", "text"),
    CONTRACT_LINES,
    ids=[f"{s.split()[0]}-line-{n}" for s, n, _ in CONTRACT_LINES],
)
def test_contract_example_validates(section: str, line_no: int, text: str) -> None:
    adapter = _ADAPTERS.get(section)
    assert adapter is not None, f"line {line_no} sits under an unknown heading: {section!r}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover
        pytest.fail(f"{CONTRACT_FILE.name} line {line_no} is not JSON: {exc}")
    try:
        adapter.validate_python(payload)
    except ValidationError as exc:
        pytest.fail(
            f"{CONTRACT_FILE.name} line {line_no} no longer matches the models.\n"
            f"{text}\n{exc}"
        )


def test_the_prose_rules_are_still_in_the_document() -> None:
    """The limits the firmware relies on are stated in the file, not only in the models."""
    text = CONTRACT_FILE.read_text(encoding="utf-8")
    assert "max 20 chars" in text
    assert "max 7 chars" in text
    assert "`green`, `amber`, `red`, `neutral`" in text
    assert "10 to 20 Hz" in text
    assert "If no `ping` for 5 s" in text
