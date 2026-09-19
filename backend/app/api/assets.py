"""The fixed asset register and the item catalog. Lane B owns both handlers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
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


@router.get("/assets", response_model=AssetListResponse)
def list_assets() -> AssetListResponse:
    not_implemented("Lane B", "The asset register")


@router.post("/assets", response_model=AssetRead)
def create_asset(body: AssetCreate) -> AssetRead:
    not_implemented("Lane B", "Adding an asset")


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: int, body: AssetUpdate) -> AssetRead:
    not_implemented("Lane B", "Editing an asset")


@router.get("/catalog", response_model=CatalogListResponse)
def list_catalog() -> CatalogListResponse:
    not_implemented("Lane B", "The item catalog")


@router.post("/catalog", response_model=CatalogItemRead)
def create_catalog_item(body: CatalogItemCreate) -> CatalogItemRead:
    not_implemented("Lane B", "Adding a catalog item")
