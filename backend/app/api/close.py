"""Period close. Lane F owns the handlers.

The close is one request: total the books, run the self-checks, and, when a check
warns or fails, let the investigator write a note about it before the row is
saved. The investigation is one model call inside the POST. That is slower than
returning first and narrating later, and it is the right trade for the demo,
because the Close page then never shows a failed check with nothing under it.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.agent import investigator
from app.config import Settings, get_settings
from app.db import get_db
from app.ledger import close as close_module
from app.schemas import CloseCheck, CloseRead, CloseRequest

router = APIRouter(prefix="/api/close", tags=["close"])


def _load_json(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def read_close(row: models.Close) -> CloseRead:
    """One saved close as the wire type the Close page reads."""
    checks = _load_json(row.checks_json, [])
    return CloseRead(
        id=row.id,
        period_start=row.period_start,
        period_end=row.period_end,
        created_at=row.created_at,
        status=row.status,
        totals=_load_json(row.totals_json, {}),
        checks=[CloseCheck.model_validate(check) for check in checks]
        if isinstance(checks, list)
        else [],
        investigation_md=row.investigation_md,
        report=_load_json(row.report_json, {}),
    )


@router.post("", response_model=CloseRead)
def run_close(
    body: CloseRequest,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CloseRead:
    """Run a close over the period and save it. Every figure comes from the tables."""

    def narrate(rows: close_module.PeriodRows, result: close_module.CloseResult) -> None:
        investigator.attach(rows, result, settings)

    result = close_module.run_close(
        session,
        body.period_start,
        body.period_end,
        settings,
        investigator=narrate,
    )
    session.commit()
    assert result.id is not None
    row = session.get(models.Close, result.id)
    assert row is not None
    return read_close(row)


@router.get("/latest", response_model=CloseRead)
def get_latest_close(session: Session = Depends(get_db)) -> CloseRead:
    """The most recent close. The Close page opens on this."""
    row = session.scalars(
        select(models.Close).order_by(models.Close.id.desc()).limit(1)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No close has been run yet.",
        )
    return read_close(row)


@router.get("/{close_id}", response_model=CloseRead)
def get_close(close_id: int, session: Session = Depends(get_db)) -> CloseRead:
    """One saved close, by id."""
    row = session.get(models.Close, close_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That close report does not exist.",
        )
    return read_close(row)
