"""The tax rules in plain language, with their citations.

`OptionScoreRead.rule_ids` and the tax memo's evidence carry ids such as ABANDON and
EWASTE. Without this route a drawer can only print the code, so this serves the one copy
of the words from `tax_rules.yaml` and nothing is retyped anywhere else.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.engine import rules as engine_rules
from app.schemas import RuleRead, RulesResponse

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=RulesResponse)
def list_rules() -> RulesResponse:
    """Every rule the engine can cite, in the order the file lists them."""
    return RulesResponse(
        rules=[
            RuleRead(
                id=rule.id,
                title=rule.title,
                plain_text=rule.plain_text,
                citation_url=rule.citation_url,
                needs_human_review=rule.needs_human_review,
            )
            for rule in engine_rules.all_rules()
        ]
    )
