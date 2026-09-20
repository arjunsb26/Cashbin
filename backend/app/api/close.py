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
from app.agent import close_memo, investigator
from app.config import Settings, get_settings
from app.db import get_db
from app.ledger import close as close_module
from app.schemas import (
    CloseCheck,
    CloseRead,
    CloseRequest,
    Form4797Block,
    ReconciliationBlock,
    RollforwardBlock,
    ToolStep,
)

router = APIRouter(prefix="/api/close", tags=["close"])


def _load_json(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _block(totals: Any, key: str, kind: type[Any]) -> Any:
    """One of Lane P's depth blocks off the saved totals, or nothing when it is absent.

    A close saved before these blocks existed still reads back, with the block empty
    rather than the whole request failing.
    """
    found = totals.get(key) if isinstance(totals, dict) else None
    if not isinstance(found, dict):
        return None
    try:
        return kind.model_validate(found)
    except ValueError:
        return None


def _steps(report: Any) -> list[ToolStep]:
    """The lookups the investigator made, off the saved report."""
    found = report.get("investigation") if isinstance(report, dict) else None
    raw = found.get("steps") if isinstance(found, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[ToolStep] = []
    for item in raw:
        try:
            out.append(ToolStep.model_validate(item))
        except ValueError:
            continue
    return out


def read_close(row: models.Close) -> CloseRead:
    """One saved close as the wire type the Close page reads."""
    checks = _load_json(row.checks_json, [])
    totals = _load_json(row.totals_json, {})
    report = _load_json(row.report_json, {})
    memo = report.get("memo_md") if isinstance(report, dict) else None
    steps = _steps(report)
    return CloseRead(
        rollforward=_block(totals, "rollforward", RollforwardBlock),
        reconciliation=_block(totals, "reconciliation", ReconciliationBlock),
        form4797=_block(totals, "form4797", Form4797Block),
        memo_md=memo if isinstance(memo, str) and memo else None,
        investigation_steps=steps,
        id=row.id,
        period_start=row.period_start,
        period_end=row.period_end,
        created_at=row.created_at,
        status=row.status,
        totals=totals,
        checks=[CloseCheck.model_validate(check) for check in checks]
        if isinstance(checks, list)
        else [],
        investigation_md=row.investigation_md,
        report=report if isinstance(report, dict) else {},
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

    def memo(result: close_module.CloseResult) -> None:
        close_memo.attach(settings, result)

    result = close_module.run_close(
        session,
        body.period_start,
        body.period_end,
        settings,
        investigator=narrate,
        memo_writer=memo,
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
