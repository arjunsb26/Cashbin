"""Live settings and the tare command. Step 0 stubs them, lanes B and A fill them."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.notify.bus import CHANNEL_BIN, get_bus
from app.schemas import BinTare, DeviceTareResponse, SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsRead)
def read_settings() -> SettingsRead:
    not_implemented("Lane B", "Reading settings")


@router.patch("/settings", response_model=SettingsRead)
def update_settings(body: SettingsUpdate) -> SettingsRead:
    not_implemented("Lane B", "Changing settings")


@router.post("/device/tare", response_model=DeviceTareResponse)
def tare_device() -> DeviceTareResponse:
    """Send the scale back to zero.

    The command goes on the `bin` channel and the bin socket forwards it. `sent` says
    whether a bin was there to receive it, so the dashboard can say "no bin connected"
    instead of pretending the button did something.
    """
    delivered = get_bus().publish(BinTare(), CHANNEL_BIN)
    return DeviceTareResponse(sent=delivered > 0)
