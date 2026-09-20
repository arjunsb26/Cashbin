"""Greenhouse gas and landfill mass per option, from EPA WARM version 16.

`warm_factors.csv` holds the workbook's own numbers in MTCO2E per short ton.
Everything downstream works in kg CO2e per kg, so the conversion happens once,
here, and is unit tested.

A material the table does not cover comes back as `None`, never as zero. An
unknown is reported as unknown.
"""

from __future__ import annotations

import csv
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.engine.records import DATA_DIR, ItemRecord, Option

FACTORS_PATH = DATA_DIR / "warm_factors.csv"

# One short ton in kilograms, the exact definition of 2000 pounds.
SHORT_TON_KG = 907.18474
METRIC_TON_KG = 1000.0


class Fate(StrEnum):
    landfill = "landfill"
    recycle = "recycle"
    compost = "compost"
    combust = "combust"
    source_reduction = "source_reduction"


# Materials WARM treats as organics, which are composted rather than recycled.
FOOD_MATERIALS: frozenset[str] = frozenset(
    {
        "food_waste",
        "food_waste_non_meat",
        "food_waste_meat",
        "beef",
        "poultry",
        "grains",
        "bread",
        "fruits_and_vegetables",
        "dairy_products",
        "mixed_organics",
    }
)


def mtco2e_per_short_ton_to_kg_per_kg(value: float) -> float:
    """WARM publishes metric tons of CO2e per short ton of material."""
    return value * METRIC_TON_KG / SHORT_TON_KG


class CarbonResult(BaseModel):
    """What one option does to the climate and to the landfill."""

    model_config = ConfigDict(frozen=True)

    kg_co2e: float | None
    kg_landfill: float
    fate: Fate
    missing_materials: tuple[str, ...] = Field(default_factory=tuple)


@lru_cache(maxsize=1)
def load_factors(path: Path | None = None) -> dict[str, dict[Fate, float | None]]:
    """Read the factor table and convert it to kg CO2e per kg."""
    source = path or FACTORS_PATH
    table: dict[str, dict[Fate, float | None]] = {}
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            material = (row.get("material") or "").strip()
            if not material:
                continue
            entry: dict[Fate, float | None] = {}
            for fate in Fate:
                cell = (row.get(fate.value) or "").strip()
                entry[fate] = mtco2e_per_short_ton_to_kg_per_kg(float(cell)) if cell else None
            table[material] = entry
    return table


def known_materials() -> frozenset[str]:
    return frozenset(load_factors())


def factor(material: str, fate: Fate) -> float | None:
    """kg CO2e per kg of this material sent to this fate, or None if unknown."""
    return load_factors().get(material, {}).get(fate)


def is_food_material(material: str) -> bool:
    return material in FOOD_MATERIALS


def is_food(record: ItemRecord) -> bool:
    """True when most of the mass is something WARM counts as organics."""
    share = sum(f for m, f in record.material_mix.items() if is_food_material(m))
    return share >= 0.5


def fate_for(option: Option, material: str) -> Fate:
    """Where this material ends up under this option.

    Reselling, donating and repairing all displace a new item being made, so
    WARM's source reduction column is the right one. Say so in the tooltip.
    """
    if option is Option.trash:
        return Fate.landfill
    if option is Option.recycle:
        return Fate.compost if is_food_material(material) else Fate.recycle
    return Fate.source_reduction


def carbon_for(record: ItemRecord, option: Option) -> CarbonResult:
    """The full carbon and landfill answer for one option."""
    if option is Option.trash:
        fate = Fate.landfill
    elif option is Option.recycle:
        fate = Fate.compost if is_food(record) else Fate.recycle
    else:
        fate = Fate.source_reduction
    total = 0.0
    missing: list[str] = []
    for material, fraction in sorted(record.material_mix.items()):
        value = factor(material, fate_for(option, material))
        if value is None:
            missing.append(material)
            continue
        total += record.mass_kg * fraction * value
    if not record.material_mix:
        missing.append("unknown material")
    return CarbonResult(
        kg_co2e=None if missing else total,
        kg_landfill=record.mass_kg if option is Option.trash else 0.0,
        fate=fate,
        missing_materials=tuple(missing),
    )


def avoided_co2e(trash_kg: float | None, option_kg: float | None) -> float | None:
    """What this option avoids against the bin, as a positive number.

    WARM's source reduction column is negative on purpose: reselling or donating displaces
    a new item being made, so the figure is emissions avoided. Printed as it stands it
    reads "emissions of -6.04 kg", which nobody can act on. This is the same fact the
    right way up, and never below zero: an option that is worse than the bin avoids
    nothing rather than avoiding a negative amount.
    """
    if trash_kg is None or option_kg is None:
        return None
    return max(0.0, trash_kg - option_kg)


def kg_co2e(record: ItemRecord, option: Option) -> float | None:
    return carbon_for(record, option).kg_co2e


def kg_landfill(record: ItemRecord, option: Option) -> float:
    return carbon_for(record, option).kg_landfill


def clear_cache() -> None:
    load_factors.cache_clear()
