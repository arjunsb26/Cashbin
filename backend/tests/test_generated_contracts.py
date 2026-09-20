"""The committed contract files must match backend/app/schemas.py.

Lane D and lane E build against contracts/api-types.ts. If someone changes a schema without
regenerating, this test goes red before the frontend starts disagreeing with the backend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from scripts.check_types import check, field_names, missing_fields  # noqa: E402
from scripts.gen_types import EXPORTED, SCHEMA_FILE, TYPES_FILE  # noqa: E402


def test_contracts_are_up_to_date() -> None:
    problems = check()
    assert not problems, (
        "\n".join(problems)
        + "\nRun: uv run --project backend python scripts/gen_types.py"
    )


def test_both_contract_files_are_committed() -> None:
    assert SCHEMA_FILE.exists()
    assert TYPES_FILE.exists()


def test_every_exported_model_is_in_the_schema() -> None:
    defs = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["$defs"]
    missing = sorted(set(EXPORTED) - set(defs))
    assert not missing, f"not exported: {missing}"


def test_the_typescript_names_the_wire_messages() -> None:
    text = TYPES_FILE.read_text(encoding="utf-8")
    for name in ("UiWeight", "PhoneResult", "ScreenResult", "EventDetail", "BrandInfo"):
        assert f"export interface {name} " in text, name


def test_a_field_named_title_survives_the_generator() -> None:
    """`title` is a JSON Schema keyword, so a field of that name is easy to lose.

    The drift check compared names, not fields, so `CloseCheck.title` vanished from the
    TypeScript while every check stayed green. One field, named after the keyword, is the
    canary for the whole class of bug.
    """
    defs = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["$defs"]
    assert "title" in defs["CloseCheck"]["properties"]
    assert "title" in field_names(TYPES_FILE.read_text(encoding="utf-8"))["CloseCheck"]


def test_every_field_reaches_the_typescript() -> None:
    """Every property of every exported model is a key on its TypeScript interface."""
    problems = missing_fields()
    assert not problems, "\n".join(problems)
