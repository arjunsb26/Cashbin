"""Dump every contract schema to contracts/api-schema.json and contracts/api-types.ts.

The dashboard and the phone page both read the TypeScript file, so the wire shape is written
once here and never retyped. Regenerate after any change to backend/app/schemas.py:

    uv run --project backend python scripts/gen_types.py

The TypeScript step shells out to json-schema-to-typescript through pnpm. When node is not
available the JSON file is still written and the script says the TypeScript was skipped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR))

from pydantic import BaseModel  # noqa: E402
from pydantic.json_schema import GenerateJsonSchema, models_json_schema  # noqa: E402

from app import schemas  # noqa: E402

CONTRACTS_DIR = REPO_DIR / "contracts"
SCHEMA_FILE = CONTRACTS_DIR / "api-schema.json"
TYPES_FILE = CONTRACTS_DIR / "api-types.ts"
JSON2TS_VERSION = "15.0.4"

# Everything a client is allowed to depend on. Order does not matter, the output is sorted.
EXPORTED: tuple[str, ...] = (
    # Wire, bin
    "BinHello",
    "BinWeight",
    "BinPong",
    "BinButton",
    "BinPing",
    "BinTare",
    "ScreenIdle",
    "ScreenThinking",
    "ScreenResult",
    "ScreenAsk",
    "ScreenOffline",
    # Wire, phone
    "PhoneHello",
    "PhonePong",
    "PhonePing",
    "PhoneResult",
    "PhoneAsk",
    "PhoneIdle",
    "AskCandidate",
    # Wire, dashboard
    "UiWeight",
    "UiEventCreated",
    "UiEventUpdated",
    "UiJournalPosted",
    "UiAskOpened",
    "UiAskResolved",
    "UiMetricsUpdated",
    "UiDeviceStatus",
    # Model output
    "VisionCandidate",
    "VisionResult",
    "MoneyRange",
    "ValueEstimate",
    # REST
    "BrandInfo",
    "HealthResponse",
    "EstimateRef",
    "EventSummary",
    "EventListResponse",
    "IdentificationRead",
    "ItemRecordRead",
    "OptionScoreRead",
    "JournalLineRead",
    "JournalEntryRead",
    "CorrectionRead",
    "EventDetail",
    "VoidResponse",
    "CorrectionCreate",
    "CorrectionResponse",
    "AssetRead",
    "AssetCreate",
    "AssetUpdate",
    "AssetListResponse",
    "CatalogItemRead",
    "CatalogItemCreate",
    "CatalogListResponse",
    "TrialBalanceRow",
    "JournalResponse",
    "RoundRead",
    "RoundListResponse",
    "SummaryResponse",
    "CloseCheck",
    "CloseRequest",
    "CloseRead",
    "SettingsRead",
    "SettingsUpdate",
    "DeviceTareResponse",
    "SimTossRequest",
    "SimTossResponse",
    "SimExpectRequest",
    "SimExpectResponse",
    "SetupResponse",
    "ErrorResponse",
)


class _StableSchema(GenerateJsonSchema):
    """Sort every generated mapping so two runs on the same models byte-match."""

    def sort(self, value: object, parent_key: str | None = None) -> object:
        return super().sort(value, parent_key)


def exported_models() -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for name in EXPORTED:
        model = getattr(schemas, name)
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            raise TypeError(f"{name} is not a pydantic model")
        models.append(model)
    return models


def _strip_property_titles(node: object) -> object:
    """Drop the title pydantic puts on every property.

    Without this the TypeScript generator emits a named alias for each property, so a file of
    sixty interfaces arrives with three hundred one-line types nobody asked for.
    """
    if isinstance(node, dict):
        cleaned = {k: _strip_property_titles(v) for k, v in node.items() if k != "title"}
        return cleaned
    if isinstance(node, list):
        return [_strip_property_titles(v) for v in node]
    return node


def build_schema() -> dict[str, object]:
    """One JSON Schema document holding every exported model under $defs."""
    _keys, combined = models_json_schema(
        [(model, "validation") for model in exported_models()],
        ref_template="#/$defs/{model}",
        schema_generator=_StableSchema,
        title="BinBooksContracts",
    )
    defs = {
        name: _strip_property_titles(body) for name, body in combined.get("$defs", {}).items()
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "BinBooksContracts",
        "description": (
            "Generated from backend/app/schemas.py. Do not edit. "
            "Run scripts/gen_types.py after any schema change."
        ),
        "type": "object",
        "additionalProperties": False,
        "properties": {name: {"$ref": f"#/$defs/{name}"} for name in sorted(defs)},
        "$defs": {name: defs[name] for name in sorted(defs)},
    }


def schema_text() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _pnpm() -> str | None:
    for candidate in ("pnpm", "pnpm.cmd"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def build_types(schema_json: str) -> str | None:
    """Run json-schema-to-typescript. Returns None when pnpm is not on this machine."""
    pnpm = _pnpm()
    if pnpm is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "api-schema.json"
        target = Path(tmp) / "api-types.ts"
        source.write_text(schema_json, encoding="utf-8")
        result = subprocess.run(
            [
                pnpm,
                "dlx",
                f"json-schema-to-typescript@{JSON2TS_VERSION}",
                "--input",
                str(source),
                "--output",
                str(target),
                "--bannerComment",
                "",
                "--additionalProperties",
                "false",
                "--unreachableDefinitions",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
            check=False,
        )
        if result.returncode != 0 or not target.exists():
            raise RuntimeError(f"json-schema-to-typescript failed: {result.stderr.strip()}")
        body = target.read_text(encoding="utf-8")
    header = (
        "/* Generated from backend/app/schemas.py by scripts/gen_types.py. Do not edit.\n"
        " * Run: uv run --project backend python scripts/gen_types.py\n"
        " */\n\n"
    )
    return header + body.lstrip("\n")


def write(check_only: bool = False) -> int:
    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    schema_json = schema_text()
    types_ts = build_types(schema_json)

    if check_only:
        problems: list[str] = []
        if not SCHEMA_FILE.exists() or SCHEMA_FILE.read_text(encoding="utf-8") != schema_json:
            problems.append(str(SCHEMA_FILE))
        if types_ts is not None and (
            not TYPES_FILE.exists() or TYPES_FILE.read_text(encoding="utf-8") != types_ts
        ):
            problems.append(str(TYPES_FILE))
        if problems:
            print("out of date: " + ", ".join(problems))
            return 1
        print("contracts are up to date")
        return 0

    SCHEMA_FILE.write_text(schema_json, encoding="utf-8")
    print(f"wrote {SCHEMA_FILE}")
    if types_ts is None:
        print("pnpm not found, TypeScript not regenerated")
        return 0
    TYPES_FILE.write_text(types_ts, encoding="utf-8")
    print(f"wrote {TYPES_FILE}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the contract files.")
    parser.add_argument("--check", action="store_true", help="Fail instead of writing.")
    args = parser.parse_args()
    return write(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
