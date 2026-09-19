"""Fail when the committed contract files no longer match backend/app/schemas.py.

The test suite calls check() on every run, so a schema change without a regenerate turns
into a red test rather than a frontend that silently disagrees with the backend.

    uv run --project backend python scripts/check_types.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR))

from scripts.gen_types import SCHEMA_FILE, TYPES_FILE, schema_text  # noqa: E402

_TS_NAME = re.compile(r"^export (?:interface|type) ([A-Za-z0-9_]+)", re.MULTILINE)


def check() -> list[str]:
    """Return one line per problem. An empty list means the contracts are current."""
    problems: list[str] = []
    expected = schema_text()

    if not SCHEMA_FILE.exists():
        problems.append(f"{SCHEMA_FILE} is missing. Run scripts/gen_types.py.")
        return problems

    actual = SCHEMA_FILE.read_text(encoding="utf-8")
    if actual != expected:
        problems.append(
            f"{SCHEMA_FILE.name} does not match backend/app/schemas.py. "
            "Run scripts/gen_types.py and commit the result."
        )

    if not TYPES_FILE.exists():
        problems.append(f"{TYPES_FILE} is missing. Run scripts/gen_types.py.")
        return problems

    # The TypeScript is generated from the JSON schema, so comparing the names it exports
    # against the names the schema defines catches a regenerate that only got half done.
    defined = set(json.loads(expected)["$defs"])
    exported = set(_TS_NAME.findall(TYPES_FILE.read_text(encoding="utf-8")))
    missing = sorted(defined - exported)
    if missing:
        problems.append(
            f"{TYPES_FILE.name} is missing {len(missing)} type(s): {', '.join(missing[:8])}. "
            "Run scripts/gen_types.py and commit the result."
        )
    return problems


def main() -> int:
    problems = check()
    for line in problems:
        print(line)
    if problems:
        return 1
    print("contracts are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
