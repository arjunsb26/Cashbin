"""Answering an ask and overriding a label. Lane C owns the handler."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.learn.corrections import CorrectionRefusedError, apply_correction
from app.schemas import CorrectionCreate, CorrectionResponse

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.post("", response_model=CorrectionResponse)
async def create_correction(body: CorrectionCreate) -> CorrectionResponse:
    """One answer from a person. The label has already been validated into a plain key."""
    try:
        return await apply_correction(body)
    except CorrectionRefusedError as refused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(refused)) from refused
