"""The seed files are data, so the tests check they parse and add up.

A cell a person still has to fill in is reported, not failed. That is what
`list_needs_human()` is for, and it is what the setup checklist reads.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.engine import carbon, rules
from app.engine.records import (
    DATA_DIR,
    ItemClass,
    catalog_by_label,
    list_needs_human,
    load_assets_seed,
    load_catalog,
    load_llm_prices,
)

ENGINE_DIR = Path(__file__).resolve().parents[1] / "app" / "engine"

# Written as code points so this file does not itself contain the characters.
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


# --- catalog -----------------------------------------------------------------


def test_the_catalog_parses_and_is_the_right_size() -> None:
    items = load_catalog()
    assert 30 <= len(items) <= 40
    assert len({item.label for item in items}) == len(items)
    assert len({item.id for item in items}) == len(items)


def test_every_material_mix_sums_to_one() -> None:
    for item in load_catalog():
        total = sum(item.material_mix.values())
        assert abs(total - 1.0) < 0.001, f"{item.label} sums to {total}"


def test_every_material_is_in_the_warm_table() -> None:
    known = carbon.known_materials()
    for item in load_catalog():
        for material in item.material_mix:
            assert material in known, f"{item.label} uses {material}"


def test_the_catalog_covers_food_packaging_and_small_electronics() -> None:
    labels = {item.label for item in load_catalog()}
    for label in ("bagel", "pizza slice", "coffee cup with lid"):
        assert label in labels
    for label in ("cardboard box small", "pizza box", "paper napkins"):
        assert label in labels
    for label in ("usb-c charger", "keyboard", "power bank", "phone"):
        assert label in labels


def test_every_electronics_row_is_flagged_and_batteries_are_flagged_too() -> None:
    table = catalog_by_label()
    electronics = (
        "usb cable",
        "usb-c charger",
        "laptop charger",
        "mouse",
        "keyboard",
        "earbuds",
        "phone",
        "hdmi cable",
        "power bank",
        "webcam",
    )
    for label in electronics:
        assert "electronics" in table[label].regulatory_flags, label
    for label in ("power bank", "phone"):
        assert "battery" in table[label].regulatory_flags, label


def test_no_food_row_is_flagged_as_electronics() -> None:
    for item in load_catalog():
        if item.item_class is ItemClass.inventory:
            assert "electronics" not in item.regulatory_flags


def test_mass_priors_start_weak_so_real_weighings_win() -> None:
    for item in load_catalog():
        assert item.mass_prior_mean_g is not None, item.label
        assert item.mass_prior_var is not None, item.label
        assert item.mass_prior_n == 1, item.label
        # A wide prior: one standard deviation is more than a third of the mean.
        assert item.mass_prior_var > (item.mass_prior_mean_g / 3) ** 2, item.label


def test_every_priced_row_names_where_the_price_came_from() -> None:
    for item in load_catalog():
        if item.unit_cost_cents is None and item.price_per_kg_cents is None:
            continue
        assert item.price_source, item.label
        assert item.price_source.startswith("http"), item.label


# --- assets ------------------------------------------------------------------


def test_the_assets_seed_is_a_template_with_nothing_invented() -> None:
    assets = load_assets_seed()
    assert len(assets) == 12
    assert len({asset.tag for asset in assets}) == 12
    for asset in assets:
        assert asset.cost_cents is None, asset.tag
        assert asset.in_service_date is None, asset.tag
        assert asset.tax_method is None, asset.tag


def test_the_demo_keyboard_is_tagged_as_the_plan_says() -> None:
    tags = {asset.tag: asset for asset in load_assets_seed()}
    assert "BB-0002" in tags
    assert "keyboard" in tags["BB-0002"].description.lower()


def test_at_least_two_assets_are_marked_as_bonus_candidates() -> None:
    noted = [a for a in load_assets_seed() if a.note and "bonus_100" in a.note]
    assert len(noted) >= 2


# --- llm prices --------------------------------------------------------------


def test_the_llm_price_file_is_three_empty_openai_rows() -> None:
    prices = load_llm_prices()
    assert len(prices) == 3
    for price in prices:
        assert price.provider == "openai"
        assert price.model is None
        assert not price.complete


# --- warm factors ------------------------------------------------------------


def test_the_warm_table_says_where_it_came_from() -> None:
    text = (DATA_DIR / "warm_factors.csv").read_text(encoding="utf-8")
    assert "WARM_v16" in text


def test_no_warm_factor_cell_is_a_guessed_zero() -> None:
    """A blank means the fate does not apply. It must load as None, not 0.0."""
    table = carbon.load_factors()
    assert table["food_waste"][carbon.Fate.recycle] is None
    assert table["food_waste"][carbon.Fate.compost] is not None


# --- rules -------------------------------------------------------------------


def test_every_rule_id_used_in_the_engine_exists_in_the_file() -> None:
    known = {rule.id for rule in rules.all_rules()}
    used: set[str] = set()
    for path in ENGINE_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        used.update(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', source))
    cited = {name for name in used if name in known}
    assert cited, "the engine cites no rules at all"
    assert cited <= known
    assert {"ABANDON", "INV_COGS", "EWASTE", "DONATE_FOOD", "DONATE_EQUIP"} <= cited


def test_every_rule_has_plain_text_a_person_can_read() -> None:
    for rule in rules.all_rules():
        assert len(rule.plain_text) > 40, rule.id
        assert "\n" not in rule.plain_text
        for banned in ("--", "->", EM_DASH, EN_DASH):
            assert banned not in rule.plain_text, rule.id


def test_the_rules_with_citations_point_at_the_sources_the_plan_names() -> None:
    assert rules.get("ABANDON").citation_url == "https://www.irs.gov/publications/p544"
    assert rules.get("RECAPTURE").citation_url == "https://www.irs.gov/instructions/i4797"
    assert len(rules.get("DONATE_FOOD").citations) == 2
    for rule in rules.all_rules():
        for url in rule.citations:
            assert url.startswith("https://")


# --- the setup checklist -----------------------------------------------------


def test_unfilled_cells_are_reported_rather_than_failing_the_suite() -> None:
    pending = list_needs_human()
    assert isinstance(pending, list)
    # Every asset row waits on cost, date and method. Three cells times twelve.
    assert sum(1 for line in pending if line.startswith("assets_seed.csv")) == 36
    assert sum(1 for line in pending if line.startswith("llm_prices.csv")) == 12
    for line in pending:
        assert line.count(":") >= 2


def test_nothing_in_the_seed_files_reads_like_filler() -> None:
    for name in ("catalog.csv", "assets_seed.csv"):
        text = (DATA_DIR / name).read_text(encoding="utf-8").lower()
        for banned in ("lorem", "acme", "john doe", "example.com", "todo", "placeholder"):
            assert banned not in text, f"{name} contains {banned}"


def test_the_data_readme_explains_every_file() -> None:
    text = (DATA_DIR / "README.md").read_text(encoding="utf-8")
    for name in (
        "catalog.csv",
        "warm_factors.csv",
        "tax_rules.yaml",
        "assets_seed.csv",
        "llm_prices.csv",
    ):
        assert name in text


def test_the_engine_modules_carry_no_dashes_a_reader_would_trip_over() -> None:
    for path in sorted(ENGINE_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            doc = ast.get_docstring(node) if isinstance(
                node, ast.Module | ast.ClassDef | ast.FunctionDef
            ) else None
            if not doc:
                continue
            for banned in (EM_DASH, EN_DASH, "->"):
                assert banned not in doc, f"{path.name}: {banned}"
