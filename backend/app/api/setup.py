"""The setup checklist: what nobody has filled in yet.

PLAN.md section 17. A cell marked `NEEDS_HUMAN` in a seed file is a number nobody has
supplied. It is never guessed and never silently treated as zero, so the dashboard has a
page that names every one of them. This route is that page's only source.

It reports and never fails. A missing seed file means fewer lines, not a 500.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.engine.records import list_needs_human
from app.schemas import SetupResponse

router = APIRouter(prefix="/api", tags=["setup"])


@router.get("/setup", response_model=SetupResponse)
def get_setup() -> SetupResponse:
    """Every seed cell still waiting on a person, one line each, file first."""
    return SetupResponse(items=list_needs_human())
