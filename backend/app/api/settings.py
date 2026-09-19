"""Live settings and the tare command.

Only the keys in RUNTIME_SETTING_KEYS can be changed while the app runs. A change is written
to the settings table and applied to the running settings object in the same call, so the
next event is identified against the new thresholds without a restart. A read applies
whatever the table holds first, which is how a change survives a restart.

Nothing about the model provider, the base URL or the key is readable or writable here.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import not_implemented
from app.config import RUNTIME_SETTING_KEYS, Settings, get_settings
from app.db import get_db
from app.models import Setting
from app.schemas import DeviceTareResponse, SettingsRead, SettingsUpdate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


def stored_overrides(session: Session) -> dict[str, object]:
    """The runtime keys the settings table holds. An unreadable row is ignored, not fatal."""
    rows = session.execute(
        select(Setting).where(Setting.key.in_(RUNTIME_SETTING_KEYS))
    ).scalars()
    out: dict[str, object] = {}
    for row in rows:
        try:
            out[row.key] = json.loads(row.value_json)
        except json.JSONDecodeError:
            log.warning("setting %s is not readable and was skipped", row.key)
    return out


def apply_overrides(active: Settings, overrides: dict[str, object]) -> Settings:
    """Validate through SettingsUpdate, then move the values onto the running settings."""
    checked = SettingsUpdate.model_validate(overrides).model_dump(exclude_none=True)
    for key, value in checked.items():
        if key in RUNTIME_SETTING_KEYS:
            setattr(active, key, value)
    return active


def current(session: Session) -> SettingsRead:
    active = apply_overrides(get_settings(), stored_overrides(session))
    return SettingsRead.model_validate(
        {key: getattr(active, key) for key in RUNTIME_SETTING_KEYS}
    )


@router.get("/settings", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_db)) -> SettingsRead:
    """What the system is running on right now."""
    return current(session)


@router.patch("/settings", response_model=SettingsRead)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_db)) -> SettingsRead:
    """Change one or more thresholds. The pipeline sees the change on the next event."""
    changes = body.model_dump(exclude_none=True)
    for key, value in changes.items():
        if key not in RUNTIME_SETTING_KEYS:
            continue
        row = session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value_json=json.dumps(value)))
        else:
            row.value_json = json.dumps(value)
    session.flush()
    apply_overrides(get_settings(), changes)
    session.commit()
    return current(session)


@router.post("/device/tare", response_model=DeviceTareResponse)
def tare_device() -> DeviceTareResponse:
    not_implemented("Lane A", "Taring the scale")
