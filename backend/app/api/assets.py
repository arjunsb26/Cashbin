"""The fixed asset register and the item catalog. Lane B owns both handlers."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.engine import depreciation
from app.engine.records import AssetInfo
from app.engine.records import AssetStatus as EngineAssetStatus
from app.engine.records import TaxMethod as EngineTaxMethod
from app.schemas import (
    AssetCreate,
    AssetListResponse,
    AssetRead,
    AssetUpdate,
    CatalogItemCreate,
    CatalogItemRead,
    CatalogListResponse,
)

router = APIRouter(prefix="/api", tags=["assets"])


def today() -> date:
    """The day the register is valued on. One place, so tests can reason about it."""
    return datetime.now(UTC).date()


def _parse_json_field(raw: str | None, fallback: object) -> object:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _in_service_date(raw: str) -> date | None:
    """The stored date, or None when the cell is not a date the engine can use."""
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def to_asset_info(row: models.Asset) -> AssetInfo:
    """The register row as the engine's own type, so depreciation is computed once."""
    return AssetInfo(
        id=row.id,
        tag=row.tag,
        description=row.description,
        category=row.category,
        cost_cents=row.cost_cents,
        in_service_date=_in_service_date(row.in_service_date),
        book_life_months=row.book_life_months,
        salvage_cents=row.salvage_cents,
        tax_method=EngineTaxMethod(row.tax_method.value),
        tax_basis_cents_override=row.tax_basis_cents_override,
        status=EngineAssetStatus(row.status.value),
        disposed_event_id=row.disposed_event_id,
        insured=row.insured,
        location=row.location,
    )


def read_asset(row: models.Asset, on: date | None = None) -> AssetRead:
    """One register row with today's book value and tax basis worked out."""
    when = on or today()
    info = to_asset_info(row)
    return AssetRead(
        id=row.id,
        tag=row.tag,
        description=row.description,
        category=row.category,
        cost_cents=row.cost_cents,
        in_service_date=row.in_service_date,
        book_life_months=row.book_life_months,
        salvage_cents=row.salvage_cents,
        tax_method=row.tax_method,
        tax_basis_cents_override=row.tax_basis_cents_override,
        status=row.status,
        disposed_event_id=row.disposed_event_id,
        insured=row.insured,
        location=row.location,
        book_value_cents=depreciation.book_value(info, when).book_value_cents,
        tax_basis_cents=depreciation.tax_basis(info, when),
    )


def read_catalog_item(row: models.CatalogItem) -> CatalogItemRead:
    mix = _parse_json_field(row.material_mix_json, {})
    flags = _parse_json_field(row.regulatory_flags_json, [])
    return CatalogItemRead(
        id=row.id,
        label=row.label,
        item_class=row.item_class,
        unit_cost_cents=row.unit_cost_cents,
        unit_mass_g=row.unit_mass_g,
        price_per_kg_cents=row.price_per_kg_cents,
        fmv_per_kg_cents=row.fmv_per_kg_cents,
        material_mix=mix if isinstance(mix, dict) else {},
        regulatory_flags=flags if isinstance(flags, list) else [],
        mass_prior_mean_g=row.mass_prior_mean_g,
        mass_prior_var=row.mass_prior_var,
        mass_prior_n=row.mass_prior_n,
    )


@router.get("/assets", response_model=AssetListResponse)
def list_assets(
    asset_status: models.AssetStatus | None = Query(
        default=None, alias="status", description="Only assets in this state."
    ),
    session: Session = Depends(get_db),
) -> AssetListResponse:
    query = select(models.Asset).order_by(models.Asset.tag)
    if asset_status is not None:
        query = query.where(models.Asset.status == asset_status)
    on = today()
    return AssetListResponse(assets=[read_asset(row, on) for row in session.scalars(query)])


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(body: AssetCreate, session: Session = Depends(get_db)) -> AssetRead:
    row = models.Asset(
        tag=body.tag,
        description=body.description,
        category=body.category,
        cost_cents=body.cost_cents,
        in_service_date=body.in_service_date,
        book_life_months=body.book_life_months,
        salvage_cents=body.salvage_cents,
        tax_method=models.TaxMethod(body.tax_method.value),
        tax_basis_cents_override=body.tax_basis_cents_override,
        status=models.AssetStatus.active,
        insured=body.insured,
        location=body.location,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An asset is already tagged {body.tag}.",
        ) from None
    return read_asset(row)


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: int, body: AssetUpdate, session: Session = Depends(get_db)
) -> AssetRead:
    row = session.get(models.Asset, asset_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That asset is not on the register."
        )
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        if field == "tax_method":
            row.tax_method = models.TaxMethod(str(value))
        elif field == "status":
            row.status = models.AssetStatus(str(value))
        else:
            setattr(row, field, value)
    session.flush()
    return read_asset(row)


@router.get("/catalog", response_model=CatalogListResponse)
def list_catalog(session: Session = Depends(get_db)) -> CatalogListResponse:
    query = select(models.CatalogItem).order_by(models.CatalogItem.label)
    return CatalogListResponse(items=[read_catalog_item(row) for row in session.scalars(query)])


@router.post("/catalog", response_model=CatalogItemRead, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    body: CatalogItemCreate, session: Session = Depends(get_db)
) -> CatalogItemRead:
    row = models.CatalogItem(
        label=body.label,
        item_class=body.item_class,
        unit_cost_cents=body.unit_cost_cents,
        unit_mass_g=body.unit_mass_g,
        price_per_kg_cents=body.price_per_kg_cents,
        fmv_per_kg_cents=body.fmv_per_kg_cents,
        material_mix_json=json.dumps(dict(body.material_mix)),
        regulatory_flags_json=json.dumps(list(body.regulatory_flags)),
        mass_prior_mean_g=body.unit_mass_g,
        mass_prior_var=None,
        mass_prior_n=0,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The catalog already has {body.label}.",
        ) from None
    return read_catalog_item(row)
