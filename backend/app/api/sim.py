"""Simulator control. Mounted only when DEV_TOOLS is on, so the demo build never shows it."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import not_implemented
from app.schemas import SimExpectRequest, SimExpectResponse, SimTossRequest, SimTossResponse

router = APIRouter(prefix="/api/sim", tags=["sim"])


@router.post("/toss", response_model=SimTossResponse)
def inject_toss(body: SimTossRequest) -> SimTossResponse:
    not_implemented("Lane A", "Injecting a toss")


@router.post("/expect", response_model=SimExpectResponse)
def set_expected(body: SimExpectRequest) -> SimExpectResponse:
    not_implemented("Lane C", "Telling the stub provider what is coming")
