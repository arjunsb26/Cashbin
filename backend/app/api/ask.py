"""Ask the books a question in plain words and get the lookups back with the answer.

Lane Z. One route. The body is validated into a small object before anything sees it,
the agent in `agent/ask.py` does the looking up, and nothing on this path writes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent import ask as ask_agent
from app.config import Settings, get_settings
from app.db import session_scope
from app.schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask_the_books(
    body: AskRequest, settings: Settings = Depends(get_settings)
) -> AskResponse:
    """Answer one question about the books, with the lookups that got there beside it.

    A question that is empty or carries anything outside the allowed characters is
    refused at the boundary, so it never reaches a model at all.
    """
    with session_scope() as session:
        return ask_agent.ask(session, body.question, settings)
