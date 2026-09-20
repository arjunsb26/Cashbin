"""Typed records the decision engine works on, and the loaders for the seed files.

Everything here is in memory. Nothing in this module talks to the database. The
field names mirror the SQL columns in PLAN.md section 8 so a row maps straight
onto a model, with two changes the plan allows: the two `_json` columns become
real typed fields, and the record carries the event date so depreciation can be
computed without a second lookup.

All money is whole cents as `int`. All masses are grams as `float`.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
NEEDS_HUMAN = "NEEDS_HUMAN"


class ItemClass(StrEnum):
    inventory = "inventory"
    fixed_asset = "fixed_asset"
    untracked = "untracked"


class Option(StrEnum):
    trash = "trash"
    recycle = "recycle"
    repair = "repair"
    resell = "resell"
    donate = "donate"


class EstimateSource(StrEnum):
    catalog = "catalog"
    register = "register"
    model_estimate = "model_estimate"
    human = "human"


class Condition(StrEnum):
    working = "working"
    broken = "broken"
    unknown = "unknown"


class TaxMethod(StrEnum):
    bonus_100 = "bonus_100"
    straight_line = "straight_line"


class AssetStatus(StrEnum):
    active = "active"
    disposed = "disposed"
    ghost_suspected = "ghost_suspected"


class Estimate(BaseModel):
    """A value nobody measured, with its range and where it came from."""

    model_config = ConfigDict(frozen=True)

    low: int
    mid: int
    high: int
    source: EstimateSource


class EngineSettings(BaseModel):
    """The tunables the engine reads. Defaults match PLAN.md section 18."""

    model_config = ConfigDict(frozen=True)

    tax_rate: float = 0.21
    disposal_fee_cents: int = 0
    recycle_fee_cents: int = 0
    capitalization_threshold_cents: int = 50000
    tie_break_cents: int = 50
    # How much better on carbon another option has to be before the tone stops
    # calling the bin a fine answer. PLAN.md section 21a item 10.
    tone_co2e_kg: float = 0.02
    # How much better another option has to be before the bin argues with a person.
    speak_up_cents: int = 100

    @classmethod
    def from_settings(cls, settings: Any) -> EngineSettings:
        """Build the engine's view from the one live settings object.

        This is the single seam between the app's configuration and the engine,
        so the two sets of numbers cannot drift. `app.config` is imported here
        and nowhere else under `engine/`, and only as a type the caller passes
        in, so the engine still has no configuration of its own to load.
        """
        return cls(
            tax_rate=settings.tax_rate,
            disposal_fee_cents=settings.disposal_fee_cents,
            recycle_fee_cents=settings.recycle_fee_cents,
            capitalization_threshold_cents=settings.capitalization_threshold_cents,
            speak_up_cents=getattr(
                settings, "speak_up_cents", cls.model_fields["speak_up_cents"].default
            ),
            tie_break_cents=getattr(
                settings, "tie_break_cents", cls.model_fields["tie_break_cents"].default
            ),
            tone_co2e_kg=getattr(
                settings, "tone_co2e_kg", cls.model_fields["tone_co2e_kg"].default
            ),
        )


class CatalogItem(BaseModel):
    """One row of `catalog_item`."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    label: str
    item_class: ItemClass = Field(alias="class")
    unit_cost_cents: int | None = None
    unit_mass_g: float | None = None
    price_per_kg_cents: int | None = None
    fmv_per_kg_cents: int | None = None
    material_mix: dict[str, float] = Field(default_factory=dict)
    regulatory_flags: list[str] = Field(default_factory=list)
    mass_prior_mean_g: float | None = None
    mass_prior_var: float | None = None
    mass_prior_n: int = 0
    price_source: str | None = None


class AssetInfo(BaseModel):
    """One row of `asset`, with the columns the engine and the ledger need."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    tag: str
    description: str
    category: str | None = None
    cost_cents: int | None = None
    in_service_date: date | None = None
    book_life_months: int | None = None
    salvage_cents: int = 0
    tax_method: TaxMethod | None = None
    tax_basis_cents_override: int | None = None
    status: AssetStatus = AssetStatus.active
    disposed_event_id: int | None = None
    insured: bool = False
    location: str | None = None
    note: str | None = None


class ItemRecord(BaseModel):
    """One row of `item_record`: what was thrown away and what it is worth."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: int
    label: str
    item_class: ItemClass = Field(alias="class")
    mass_g: float
    event_date: date

    material_mix: dict[str, float] = Field(default_factory=dict)
    regulatory_flags: list[str] = Field(default_factory=list)

    book_value_cents: int = 0
    tax_basis_cents: int = 0
    asset_id: int | None = None
    cost_basis_cents: int | None = None

    fmv_low: int | None = None
    fmv_mid: int | None = None
    fmv_high: int | None = None
    fmv_source: EstimateSource | None = None

    repair_low: int | None = None
    repair_mid: int | None = None
    repair_high: int | None = None
    repair_source: EstimateSource | None = None

    replacement_cents: int | None = None
    replacement_source: EstimateSource | None = None

    scrap_cents: int | None = None
    scrap_source: EstimateSource | None = None

    condition: Condition = Condition.unknown
    # What the model said it was looking at, and anything a person answered about it.
    # Both are outside text and both are read here only for words like "sealed".
    description: str = ""
    detail: str = ""

    @property
    def mass_kg(self) -> float:
        return self.mass_g / 1000.0

    @property
    def fmv(self) -> Estimate | None:
        if self.fmv_mid is None or self.fmv_source is None:
            return None
        return Estimate(
            low=self.fmv_low if self.fmv_low is not None else self.fmv_mid,
            mid=self.fmv_mid,
            high=self.fmv_high if self.fmv_high is not None else self.fmv_mid,
            source=self.fmv_source,
        )

    @property
    def repair(self) -> Estimate | None:
        if self.repair_mid is None or self.repair_source is None:
            return None
        return Estimate(
            low=self.repair_low if self.repair_low is not None else self.repair_mid,
            mid=self.repair_mid,
            high=self.repair_high if self.repair_high is not None else self.repair_mid,
            source=self.repair_source,
        )

    def has_flag(self, flag: str) -> bool:
        return flag in self.regulatory_flags


class OptionScore(BaseModel):
    """One row of `option_score`: one possible fate, fully priced."""

    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    event_id: int | None = None
    option: Option
    allowed: bool = True
    blocked_reason: str | None = None
    cash_cents: int = 0
    tax_effect_cents: int = 0
    net_after_tax_cents: int = 0
    kg_co2e: float | None = None
    kg_landfill: float = 0.0
    needs_human_review: bool = False
    notes: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    rank: int | None = None


def _cost_basis_from_catalog(catalog: CatalogItem, mass_g: float) -> int | None:
    """What the tossed mass cost, by the best rule the catalog row supports."""
    if catalog.price_per_kg_cents is not None:
        return round(catalog.price_per_kg_cents * mass_g / 1000.0)
    if catalog.unit_cost_cents is None:
        return None
    if catalog.unit_mass_g:
        return round(catalog.unit_cost_cents * mass_g / catalog.unit_mass_g)
    return catalog.unit_cost_cents


def _fmv_from_catalog(catalog: CatalogItem, mass_g: float) -> int | None:
    if catalog.fmv_per_kg_cents is None:
        return None
    return round(catalog.fmv_per_kg_cents * mass_g / 1000.0)


def build_item_record(
    *,
    event_id: int,
    label: str,
    item_class: ItemClass,
    mass_g: float,
    event_date: date,
    catalog: CatalogItem | None = None,
    asset: AssetInfo | None = None,
    condition: Condition = Condition.unknown,
    fmv: Estimate | None = None,
    repair: Estimate | None = None,
    replacement_cents: int | None = None,
    replacement_source: EstimateSource | None = None,
    scrap_cents: int | None = None,
    scrap_source: EstimateSource | None = None,
    material_mix: dict[str, float] | None = None,
    regulatory_flags: list[str] | None = None,
    description: str = "",
    detail: str = "",
) -> ItemRecord:
    """Assemble the record the engine scores.

    Book value and tax basis come from the asset register for a fixed asset and
    are zero for everything else. Cost basis comes from the catalog row. An
    estimate passed in wins over the catalog, because a person or a model looked
    at this particular object.
    """
    from app.engine import depreciation

    mix = dict(material_mix) if material_mix is not None else {}
    flags = list(regulatory_flags) if regulatory_flags is not None else []
    if catalog is not None:
        if not mix:
            mix = dict(catalog.material_mix)
        if not flags:
            flags = list(catalog.regulatory_flags)

    book_value_cents = 0
    tax_basis_cents = 0
    cost_basis_cents: int | None = None

    if item_class is ItemClass.fixed_asset and asset is not None:
        book_value_cents = depreciation.book_value(asset, event_date).book_value_cents
        tax_basis_cents = depreciation.tax_basis(asset, event_date)
    elif item_class is ItemClass.inventory and catalog is not None:
        cost_basis_cents = _cost_basis_from_catalog(catalog, mass_g)

    if fmv is None and catalog is not None:
        catalog_fmv = _fmv_from_catalog(catalog, mass_g)
        if catalog_fmv is not None:
            fmv = Estimate(
                low=catalog_fmv,
                mid=catalog_fmv,
                high=catalog_fmv,
                source=EstimateSource.catalog,
            )

    return ItemRecord(
        event_id=event_id,
        label=label,
        item_class=item_class,
        mass_g=mass_g,
        event_date=event_date,
        material_mix=mix,
        regulatory_flags=flags,
        book_value_cents=book_value_cents,
        tax_basis_cents=tax_basis_cents,
        asset_id=asset.id if asset is not None else None,
        cost_basis_cents=cost_basis_cents,
        fmv_low=fmv.low if fmv else None,
        fmv_mid=fmv.mid if fmv else None,
        fmv_high=fmv.high if fmv else None,
        fmv_source=fmv.source if fmv else None,
        repair_low=repair.low if repair else None,
        repair_mid=repair.mid if repair else None,
        repair_high=repair.high if repair else None,
        repair_source=repair.source if repair else None,
        replacement_cents=replacement_cents,
        replacement_source=replacement_source,
        scrap_cents=scrap_cents,
        scrap_source=scrap_source,
        condition=condition,
        description=description,
        detail=detail,
    )


# --- seed file loaders -------------------------------------------------------


def _blank(value: str | None) -> bool:
    return value is None or value.strip() == "" or value.strip() == NEEDS_HUMAN


def _opt_int(value: str | None) -> int | None:
    return None if _blank(value) else int(str(value).strip())


def _opt_float(value: str | None) -> float | None:
    return None if _blank(value) else float(str(value).strip())


def _opt_str(value: str | None) -> str | None:
    return None if value is None or value.strip() == "" else value.strip()


def _opt_date(value: str | None) -> date | None:
    return None if _blank(value) else date.fromisoformat(str(value).strip())


def _opt_bool(value: str | None) -> bool:
    return not _blank(value) and str(value).strip().lower() in {"1", "true", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=1)
def load_catalog(path: Path | None = None) -> tuple[CatalogItem, ...]:
    """Read `catalog.csv`. Cached, because it never changes while the app runs."""
    rows = _read_csv(path or DATA_DIR / "catalog.csv")
    items: list[CatalogItem] = []
    for row in rows:
        mix_raw = row.get("material_mix_json") or "{}"
        flags_raw = row.get("regulatory_flags_json") or "[]"
        items.append(
            CatalogItem(
                id=int(row["id"]),
                label=row["label"].strip(),
                item_class=ItemClass(row["class"].strip()),
                unit_cost_cents=_opt_int(row.get("unit_cost_cents")),
                unit_mass_g=_opt_float(row.get("unit_mass_g")),
                price_per_kg_cents=_opt_int(row.get("price_per_kg_cents")),
                fmv_per_kg_cents=_opt_int(row.get("fmv_per_kg_cents")),
                material_mix=json.loads(mix_raw) if mix_raw.strip() else {},
                regulatory_flags=json.loads(flags_raw) if flags_raw.strip() else [],
                mass_prior_mean_g=_opt_float(row.get("mass_prior_mean_g")),
                mass_prior_var=_opt_float(row.get("mass_prior_var")),
                mass_prior_n=_opt_int(row.get("mass_prior_n")) or 0,
                price_source=_opt_str(row.get("price_source")),
            )
        )
    return tuple(items)


@lru_cache(maxsize=1)
def load_assets_seed(path: Path | None = None) -> tuple[AssetInfo, ...]:
    """Read `assets_seed.csv`. Unfilled cells stay empty, never a made-up number."""
    rows = _read_csv(path or DATA_DIR / "assets_seed.csv")
    assets: list[AssetInfo] = []
    for row in rows:
        method = _opt_str(row.get("tax_method"))
        assets.append(
            AssetInfo(
                id=int(row["id"]),
                tag=row["tag"].strip(),
                description=row["description"].strip(),
                category=_opt_str(row.get("category")),
                cost_cents=_opt_int(row.get("cost_cents")),
                in_service_date=_opt_date(row.get("in_service_date")),
                book_life_months=_opt_int(row.get("book_life_months")),
                salvage_cents=_opt_int(row.get("salvage_cents")) or 0,
                tax_method=(
                    TaxMethod(method) if method and method != NEEDS_HUMAN else None
                ),
                tax_basis_cents_override=_opt_int(row.get("tax_basis_cents_override")),
                status=AssetStatus(_opt_str(row.get("status")) or "active"),
                disposed_event_id=_opt_int(row.get("disposed_event_id")),
                insured=_opt_bool(row.get("insured")),
                location=_opt_str(row.get("location")),
                note=_opt_str(row.get("note")),
            )
        )
    return tuple(assets)


class LlmPrice(BaseModel):
    """One row of `llm_prices.csv`, used by the cost chart."""

    provider: str
    model: str | None = None
    input_usd_per_million: float | None = None
    cached_input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    source: str | None = None

    @property
    def complete(self) -> bool:
        return bool(
            self.model
            and self.input_usd_per_million is not None
            and self.output_usd_per_million is not None
        )


@lru_cache(maxsize=1)
def load_llm_prices(path: Path | None = None) -> tuple[LlmPrice, ...]:
    rows = _read_csv(path or DATA_DIR / "llm_prices.csv")
    return tuple(
        LlmPrice(
            provider=row["provider"].strip(),
            model=_opt_str(row.get("model")) if row.get("model") != NEEDS_HUMAN else None,
            input_usd_per_million=_opt_float(row.get("input_usd_per_million")),
            cached_input_usd_per_million=_opt_float(row.get("cached_input_usd_per_million")),
            output_usd_per_million=_opt_float(row.get("output_usd_per_million")),
            source=_opt_str(row.get("source")),
        )
        for row in rows
    )


def _scan_needs_human(path: Path, key_field: str) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for row in _read_csv(path):
        key = (row.get(key_field) or "?").strip() or "?"
        for field, value in row.items():
            if value is not None and value.strip() == NEEDS_HUMAN:
                out.append(f"{path.name}: {key}: {field}")
    return out


def list_needs_human(data_dir: Path | None = None) -> list[str]:
    """Every cell a person still has to fill in, as one line each.

    The setup checklist reads this. It reports, it never fails, so an unfilled
    cell is visible instead of quietly becoming a fake number.
    """
    root = data_dir or DATA_DIR
    found: list[str] = []
    found += _scan_needs_human(root / "catalog.csv", "label")
    found += _scan_needs_human(root / "assets_seed.csv", "tag")
    found += _scan_needs_human(root / "llm_prices.csv", "provider")
    found += _scan_needs_human(root / "warm_factors.csv", "material")
    return found


def clear_caches() -> None:
    """Drop the cached seed files. Used by tests that point at a fixture folder."""
    load_catalog.cache_clear()
    load_assets_seed.cache_clear()
    load_llm_prices.cache_clear()


def catalog_by_label(path: Path | None = None) -> dict[str, CatalogItem]:
    return {item.label: item for item in load_catalog(path)}


def as_row(model: BaseModel) -> dict[str, Any]:
    """Model to a dict keyed by the SQL column names, for the glue layer."""
    return model.model_dump(by_alias=True, mode="json")
