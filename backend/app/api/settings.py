"""Live settings and the tare command. Step 0 stubs them, lanes B and A fill them."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.schemas import DeviceTareResponse, SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsRead)
def read_settings() -> SettingsRead:
    not_implemented("Lane B", "Reading settings")


@router.patch("/settings", response_model=SettingsRead)
def update_settings(body: SettingsUpdate) -> SettingsRead:
    not_implemented("Lane B", "Changing settings")


@router.post("/device/tare", response_model=DeviceTareResponse)
def tare_device() -> DeviceTareResponse:
    not_implemented("Lane A", "Taring the scale")
