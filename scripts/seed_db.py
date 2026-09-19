"""Load the seed CSVs into the database. Safe to run again and again.

    uv run --project backend python scripts/seed_db.py

The catalog is upserted by label and the register by tag, so a second run
updates rather than duplicates. A cell marked `NEEDS_HUMAN` becomes an empty
column where the table allows one. An asset row whose cost, in service date or
tax method is still `NEEDS_HUMAN` cannot be stored at all, because those columns
are required, so the row is skipped and named on the way past. Pass
`--allow-placeholders` to store it with an obvious stand in instead, which is
what the setup checklist then chases.

`seed_all(session)` is the same work without the command line, for the app to
call on a first start when the tables are empty.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR))

from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402
from app.engine.records import (  # noqa: E402
    AssetInfo,
    CatalogItem,
    clear_caches,
    load_assets_seed,
    load_catalog,
)

# What a placeholder looks like when `--allow-placeholders` is given. Zero cost
# and today's date are obviously not real, which is the point: the row is
# visible on the register and on the setup checklist until a person fixes it.
PLACEHOLDER_COST_CENTS = 0
PLACEHOLDER_TAX_METHOD = models.TaxMethod.straight_line


class TableResult(BaseModel):
    """What one table's pass did."""

    table: str
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    skipped_rows: list[str] = Field(default_factory=list)


class SeedSummary(BaseModel):
    """What the whole run did, for the printed table and for tests."""

    results: list[TableResult] = Field(default_factory=list)

    @property
    def inserted(self) -> int:
        return sum(result.inserted for result in self.results)

    @property
    def updated(self) -> int:
        return sum(result.updated for result in self.results)

    @property
    def skipped(self) -> int:
        return sum(result.skipped for result in self.results)

    @property
    def skipped_rows(self) -> list[str]:
        rows: list[str] = []
        for result in self.results:
            rows.extend(result.skipped_rows)
        return rows


def _today() -> date:
    return datetime.now(UTC).date()


def seed_catalog(session: Session, items: tuple[CatalogItem, ...]) -> TableResult:
    """Upsert every catalog row by its label."""
    result = TableResult(table="catalog_item")
    existing = {
        row.label: row for row in session.scalars(select(models.CatalogItem))
    }
    for item in items:
        row = existing.get(item.label)
        if row is None:
            row = models.CatalogItem(label=item.label, item_class=item.item_class.value)
            session.add(row)
            result.inserted += 1
        else:
            result.updated += 1
        row.item_class = models.ItemClass(item.item_class.value)
        row.unit_cost_cents = item.unit_cost_cents
        row.unit_mass_g = item.unit_mass_g
        row.price_per_kg_cents = item.price_per_kg_cents
        row.fmv_per_kg_cents = item.fmv_per_kg_cents
        row.material_mix_json = json.dumps(item.material_mix)
        row.regulatory_flags_json = json.dumps(item.regulatory_flags)
        row.mass_prior_mean_g = item.mass_prior_mean_g
        row.mass_prior_var = item.mass_prior_var
        row.mass_prior_n = item.mass_prior_n
    session.flush()
    return result


def _missing_required(asset: AssetInfo) -> list[str]:
    """The required columns this row cannot fill, in the order the CSV has them."""
    missing: list[str] = []
    if asset.cost_cents is None:
        missing.append("cost_cents")
    if asset.in_service_date is None:
        missing.append("in_service_date")
    if not asset.book_life_months:
        missing.append("book_life_months")
    if asset.tax_method is None:
        missing.append("tax_method")
    return missing


def seed_assets(
    session: Session,
    assets: tuple[AssetInfo, ...],
    allow_placeholders: bool = False,
) -> TableResult:
    """Upsert every register row by its tag, skipping the ones nobody has filled in."""
    result = TableResult(table="asset")
    existing = {row.tag: row for row in session.scalars(select(models.Asset))}
    for asset in assets:
        missing = _missing_required(asset)
        if missing and not allow_placeholders:
            result.skipped += 1
            result.skipped_rows.append(
                f"{asset.tag} {asset.description}: still waiting on {', '.join(missing)}"
            )
            continue

        row = existing.get(asset.tag)
        if row is None:
            row = models.Asset(tag=asset.tag, description=asset.description)
            session.add(row)
            result.inserted += 1
        else:
            result.updated += 1
        row.description = asset.description
        row.category = asset.category
        row.cost_cents = (
            asset.cost_cents if asset.cost_cents is not None else PLACEHOLDER_COST_CENTS
        )
        row.in_service_date = (
            asset.in_service_date.isoformat()
            if asset.in_service_date is not None
            else _today().isoformat()
        )
        row.book_life_months = asset.book_life_months or 36
        row.salvage_cents = asset.salvage_cents
        row.tax_method = (
            models.TaxMethod(asset.tax_method.value)
            if asset.tax_method is not None
            else PLACEHOLDER_TAX_METHOD
        )
        row.tax_basis_cents_override = asset.tax_basis_cents_override
        row.status = models.AssetStatus(asset.status.value)
        row.insured = asset.insured
        row.location = asset.location
    session.flush()
    return result


def seed_all(
    session: Session,
    allow_placeholders: bool = False,
    data_dir: Path | None = None,
) -> SeedSummary:
    """Load both seed files into this session. The caller commits."""
    if data_dir is not None:
        clear_caches()
        items = load_catalog(data_dir / "catalog.csv")
        assets = load_assets_seed(data_dir / "assets_seed.csv")
    else:
        items = load_catalog()
        assets = load_assets_seed()

    return SeedSummary(
        results=[
            seed_catalog(session, items),
            seed_assets(session, assets, allow_placeholders),
        ]
    )


def is_empty(session: Session) -> bool:
    """True when neither seeded table has a row, which is when a first start seeds."""
    catalog_rows = session.scalar(select(func.count()).select_from(models.CatalogItem)) or 0
    asset_rows = session.scalar(select(func.count()).select_from(models.Asset)) or 0
    return catalog_rows == 0 and asset_rows == 0


def format_summary(summary: SeedSummary) -> str:
    """The table the command line prints. Plain text, one row per table."""
    lines = [
        f"{'table':<14}{'inserted':>10}{'updated':>10}{'skipped':>10}",
        f"{'-' * 14}{'-' * 10:>10}{'-' * 10:>10}{'-' * 10:>10}",
    ]
    for result in summary.results:
        lines.append(
            f"{result.table:<14}{result.inserted:>10}{result.updated:>10}{result.skipped:>10}"
        )
    lines.append(
        f"{'total':<14}{summary.inserted:>10}{summary.updated:>10}{summary.skipped:>10}"
    )
    if summary.skipped_rows:
        lines.append("")
        lines.append("Skipped, because a person has not filled these in yet:")
        lines.extend(f"  {row}" for row in summary.skipped_rows)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the seed CSVs into the database.")
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Store an unfilled asset row with an obvious stand in rather than skipping it.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Read the CSVs from here instead of backend/data.",
    )
    args = parser.parse_args(argv)

    from app.db import init_db, session_scope

    init_db()
    with session_scope() as session:
        summary = seed_all(session, args.allow_placeholders, args.data_dir)
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
