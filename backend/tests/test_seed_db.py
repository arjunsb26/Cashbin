"""The seed script: idempotent, honest about what it could not fill in."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.db import init_db, session_scope
from app.engine.records import clear_caches
from scripts.seed_db import format_summary, is_empty, main, seed_all


@pytest.fixture(autouse=True)
def _fresh_caches() -> None:
    clear_caches()


def _counts(session: Session) -> tuple[int, int]:
    catalog = session.scalar(select(func.count()).select_from(models.CatalogItem)) or 0
    assets = session.scalar(select(func.count()).select_from(models.Asset)) or 0
    return catalog, assets


def test_seeding_twice_leaves_the_same_row_counts(settings: Settings) -> None:
    init_db(settings)
    with session_scope() as session:
        first = seed_all(session)
        counts_after_first = _counts(session)
    with session_scope() as session:
        second = seed_all(session)
        counts_after_second = _counts(session)

    assert counts_after_first == counts_after_second
    assert first.inserted == 62
    assert first.updated == 0
    assert second.inserted == 0
    assert second.updated == 62


def test_the_catalog_lands_with_its_mix_and_flags(settings: Settings) -> None:
    init_db(settings)
    with session_scope() as session:
        seed_all(session)
    with session_scope() as session:
        bagel = session.scalar(
            select(models.CatalogItem).where(models.CatalogItem.label == "bagel")
        )
        assert bagel is not None
        assert bagel.item_class is models.ItemClass.inventory
        assert bagel.unit_cost_cents == 33
        assert bagel.fmv_per_kg_cents == 695
        assert bagel.material_mix_json == '{"food_waste": 1.0}'
        assert bagel.regulatory_flags_json == '["food"]'


def _data_dir_with_one_unfilled_asset(tmp_path: Path) -> Path:
    """A copy of the seed data where one register row still says NEEDS_HUMAN."""
    src = Path(__file__).resolve().parents[1] / "data"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for name in ("catalog.csv", "warm_factors.csv", "tax_rules.yaml", "llm_prices.csv"):
        (data_dir / name).write_bytes((src / name).read_bytes())
    lines = (src / "assets_seed.csv").read_text(encoding="utf-8").splitlines()
    header, first = lines[0], lines[1].split(",")
    first[4], first[5], first[8] = "NEEDS_HUMAN", "NEEDS_HUMAN", "NEEDS_HUMAN"
    (data_dir / "assets_seed.csv").write_text(
        header + "\n" + ",".join(first) + "\n", encoding="utf-8"
    )
    return data_dir


def test_an_unfilled_asset_row_is_skipped_and_named(settings: Settings, tmp_path: Path) -> None:
    init_db(settings)
    data_dir = _data_dir_with_one_unfilled_asset(tmp_path)
    with session_scope() as session:
        summary = seed_all(session, data_dir=data_dir)
    assets = next(r for r in summary.results if r.table == "asset")
    assert assets.inserted == 0
    assert assets.skipped == 1
    assert "BB-0001" in assets.skipped_rows[0]
    assert "cost_cents" in assets.skipped_rows[0]
    assert "in_service_date" in assets.skipped_rows[0]
    assert "tax_method" in assets.skipped_rows[0]


def test_placeholders_store_the_row_with_an_obvious_stand_in(
    settings: Settings, tmp_path: Path
) -> None:
    init_db(settings)
    data_dir = _data_dir_with_one_unfilled_asset(tmp_path)
    with session_scope() as session:
        summary = seed_all(session, allow_placeholders=True, data_dir=data_dir)
    assets = next(r for r in summary.results if r.table == "asset")
    assert assets.inserted == 1
    assert assets.skipped == 0

    with session_scope() as session:
        row = session.scalar(select(models.Asset).where(models.Asset.tag == "bb-0001"))
        assert row is not None
        assert row.cost_cents == 0
        assert row.tax_method is models.TaxMethod.straight_line
        assert row.status is models.AssetStatus.active


def test_the_filled_register_lands_with_real_values(settings: Settings) -> None:
    init_db(settings)
    with session_scope() as session:
        summary = seed_all(session)
    assets = next(r for r in summary.results if r.table == "asset")
    assert assets.inserted == 12
    assert assets.skipped == 0
    with session_scope() as session:
        row = session.scalar(select(models.Asset).where(models.Asset.tag == "bb-0002"))
        assert row is not None
        assert row.cost_cents == 13000
        assert row.tax_method is models.TaxMethod.bonus_100
        assert row.in_service_date == "2025-03-14"


def test_placeholder_rows_upsert_rather_than_duplicate(settings: Settings) -> None:
    init_db(settings)
    with session_scope() as session:
        seed_all(session, allow_placeholders=True)
    with session_scope() as session:
        second = seed_all(session, allow_placeholders=True)
        catalog, assets = _counts(session)
    assert second.inserted == 0
    assert second.updated == 62
    assert (catalog, assets) == (50, 12)


def test_an_empty_database_is_reported_as_empty(settings: Settings) -> None:
    init_db(settings)
    with session_scope() as session:
        assert is_empty(session) is True
        seed_all(session)
    with session_scope() as session:
        assert is_empty(session) is False


def test_the_summary_table_names_every_table_and_the_skipped_rows(
    settings: Settings, tmp_path: Path
) -> None:
    init_db(settings)
    data_dir = _data_dir_with_one_unfilled_asset(tmp_path)
    with session_scope() as session:
        summary = seed_all(session, data_dir=data_dir)
    text = format_summary(summary)
    assert "catalog_item" in text
    assert "asset" in text
    assert "inserted" in text and "updated" in text and "skipped" in text
    assert "BB-0001" in text
    assert "total" in text


def test_the_command_line_run_prints_the_summary(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([]) == 0
    first = capsys.readouterr().out
    assert "catalog_item" in first
    assert main([]) == 0
    second = capsys.readouterr().out
    assert "catalog_item" in second


def test_a_seeded_catalog_is_served_by_the_api(settings: Settings, client: TestClient) -> None:
    with session_scope() as session:
        seed_all(session)
    items = client.get("/api/catalog").json()["items"]
    assert len(items) == 50
    labels = [item["label"] for item in items]
    assert labels == sorted(labels)
    bagel = next(item for item in items if item["label"] == "bagel")
    assert bagel["regulatory_flags"] == ["food"]


def test_a_seeded_register_is_served_by_the_api(settings: Settings, client: TestClient) -> None:
    with session_scope() as session:
        seed_all(session, allow_placeholders=True)
    assets = client.get("/api/assets").json()["assets"]
    assert len(assets) == 12
    for row in assets:
        assert row["book_value_cents"] is not None
        assert row["tax_basis_cents"] is not None


def test_a_custom_data_dir_is_read_instead(settings: Settings, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "catalog.csv").write_text(
        "id,label,class,unit_cost_cents,unit_mass_g,price_per_kg_cents,fmv_per_kg_cents,"
        "material_mix_json,regulatory_flags_json,mass_prior_mean_g,mass_prior_var,"
        "mass_prior_n,price_source\n"
        '1,test bun,inventory,10,50.0,,200,"{""food_waste"":1.0}","[""food""]",50.0,900.0,1,'
        "NEEDS_HUMAN\n",
        encoding="utf-8",
    )
    (data / "assets_seed.csv").write_text(
        "id,tag,description,category,cost_cents,in_service_date,book_life_months,"
        "salvage_cents,tax_method,tax_basis_cents_override,status,disposed_event_id,"
        "insured,location,note\n"
        "1,BB-9001,Test rig,tool,5000,2025-06-01,36,0,bonus_100,,active,,false,bench,\n",
        encoding="utf-8",
    )
    init_db(settings)
    with session_scope() as session:
        summary = seed_all(session, data_dir=data)
        catalog, assets = _counts(session)
    assert summary.skipped == 0
    assert (catalog, assets) == (1, 1)
    clear_caches()


def test_a_mixed_case_tag_is_stored_lowercase_and_upserts(
    settings: Settings, tmp_path: Path
) -> None:
    """Tags are lowercase everywhere: the API lowercases them and so does the seed."""
    data = tmp_path / "mixed"
    data.mkdir()
    (data / "catalog.csv").write_text(
        "id,label,class,unit_cost_cents,unit_mass_g,price_per_kg_cents,fmv_per_kg_cents,"
        "material_mix_json,regulatory_flags_json,mass_prior_mean_g,mass_prior_var,"
        "mass_prior_n,price_source\n",
        encoding="utf-8",
    )
    (data / "assets_seed.csv").write_text(
        "id,tag,description,category,cost_cents,in_service_date,book_life_months,"
        "salvage_cents,tax_method,tax_basis_cents_override,status,disposed_event_id,"
        "insured,location,note\n"
        "1,BB-0002,Mechanical keyboard,peripheral,12000,2025-03-15,36,0,bonus_100,,"
        "active,,false,hack table,\n",
        encoding="utf-8",
    )
    init_db(settings)
    with session_scope() as session:
        first = seed_all(session, data_dir=data)
    assert first.inserted == 1

    with session_scope() as session:
        row = session.scalar(select(models.Asset).where(models.Asset.tag == "bb-0002"))
        assert row is not None
        assert row.description == "Mechanical keyboard"
        assert session.scalar(
            select(models.Asset).where(models.Asset.tag == "BB-0002")
        ) is None

    with session_scope() as session:
        second = seed_all(session, data_dir=data)
        _, assets = _counts(session)
    assert second.inserted == 0
    assert second.updated == 1
    assert assets == 1
    clear_caches()


def test_the_seeded_register_matches_what_the_api_would_store(
    settings: Settings, client: TestClient
) -> None:
    with session_scope() as session:
        seed_all(session, allow_placeholders=True)
    tags = [row["tag"] for row in client.get("/api/assets").json()["assets"]]
    assert tags == sorted(tags)
    for tag in tags:
        assert tag == tag.lower(), tag
    assert "bb-0002" in tags
