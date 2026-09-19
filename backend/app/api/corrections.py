"""Answering an ask and overriding a label. Lane C owns the handler."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.schemas import CorrectionCreate, CorrectionResponse

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.post("", response_model=CorrectionResponse)
def create_correction(body: CorrectionCreate) -> CorrectionResponse:
    not_implemented("Lane C", "Answering an ask")
