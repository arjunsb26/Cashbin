"""Loader for `tax_rules.yaml`.

The rule text here is the only copy. The evidence drawer, the close report and
any tooltip all read it from this module, so nothing is retyped anywhere else
and nothing can drift out of step with the engine.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.engine.records import DATA_DIR

RULES_PATH = DATA_DIR / "tax_rules.yaml"


class Rule(BaseModel):
    """One tax rule, as a person reads it."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    plain_text: str
    citation_url: str | None = None
    extra_citation_urls: tuple[str, ...] = Field(default_factory=tuple)
    needs_human_review: bool = False

    @property
    def citations(self) -> tuple[str, ...]:
        first = (self.citation_url,) if self.citation_url else ()
        return first + self.extra_citation_urls


class UnknownRule(KeyError):  # noqa: N818
    """Raised when code cites a rule id that is not in the file."""


@lru_cache(maxsize=1)
def load_rules(path: Path | None = None) -> dict[str, Rule]:
    source = path or RULES_PATH
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    out: dict[str, Rule] = {}
    for entry in raw.get("rules", []):
        rule = Rule(
            id=str(entry["id"]).strip(),
            title=str(entry["title"]).strip(),
            plain_text=" ".join(str(entry["plain_text"]).split()),
            citation_url=entry.get("citation_url") or None,
            extra_citation_urls=tuple(entry.get("extra_citation_urls") or ()),
            needs_human_review=bool(entry.get("needs_human_review", False)),
        )
        out[rule.id] = rule
    return out


def get(rule_id: str) -> Rule:
    """The rule with this id, or `UnknownRule` if the file does not have it."""
    rules = load_rules()
    try:
        return rules[rule_id]
    except KeyError:
        raise UnknownRule(rule_id) from None


def all_rules() -> list[Rule]:
    return list(load_rules().values())


def describe(rule_ids: list[str]) -> list[Rule]:
    """Turn the rule ids stored on an option into what the drawer shows."""
    return [get(rule_id) for rule_id in rule_ids]


def clear_cache() -> None:
    load_rules.cache_clear()
