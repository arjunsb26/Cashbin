"""One place that talks to the agent model, so three callers do not each build a client.

The investigator built its own client before this existed and still does, because it
also runs a tool loop. Everything here is the single-shot shape: fixed instruction
text this code wrote, one JSON data block of figures this code computed, a strict
schema back, and a validation pass before anything is stored.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.identify.openai_provider import PROVIDER_NAME as PROVIDER_NAME
from app.identify.openai_request import strict_schema

log = logging.getLogger(__name__)

STUB_PROVIDER = "stub"
DEFAULT_EFFORT = "low"


class CallResult(BaseModel):
    """What one call produced, and what it cost. Provider and model are always carried."""

    provider: str = STUB_PROVIDER
    model: str = ""
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


def uses_model(settings: Settings) -> bool:
    """True when a real agent model is configured. Otherwise the stub path runs."""
    return bool(
        settings.llm_provider == PROVIDER_NAME
        and settings.llm_agent_model
        and settings.openai_api_key
    )


def build_client(settings: Settings) -> Any:
    """The OpenAI client, built the way every other adapter in this app builds it."""
    from openai import OpenAI

    key = settings.openai_api_key
    base_url = settings.llm_base_url
    return OpenAI(api_key=key, base_url=base_url) if base_url else OpenAI(api_key=key)


def response_format(name: str, model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "schema": strict_schema(model), "strict": True},
    }


def messages(system: str, task: str, block: Any) -> list[dict[str, Any]]:
    """The two messages every single-shot call sends.

    The block goes in its own content part as JSON, so a label somebody typed is a
    quoted value rather than a line of the instruction.
    """
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": task},
                {
                    "type": "text",
                    "text": json.dumps(block, ensure_ascii=True, sort_keys=True, default=str),
                },
            ],
        },
    ]


def ask_once[Reply: BaseModel](
    settings: Settings,
    client: Any,
    payload: list[dict[str, Any]],
    schema_name: str,
    schema: type[Reply],
    effort: str = DEFAULT_EFFORT,
) -> tuple[Reply | None, CallResult]:
    """One call, one validated object or nothing. Never raises into the caller."""
    model = settings.llm_agent_model
    started = time.perf_counter()
    try:
        reply = client.chat.completions.create(
            model=model,
            messages=payload,
            response_format=response_format(schema_name, schema),
            reasoning_effort=effort,
            timeout=settings.llm_timeout_s,
        )
    except Exception:
        log.warning("the agent model could not be reached, writing the plain text instead")
        return None, CallResult(provider=STUB_PROVIDER, model=model)

    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = getattr(reply, "usage", None)
    result = CallResult(
        provider=PROVIDER_NAME,
        model=model,
        latency_ms=latency_ms,
        tokens_in=getattr(usage, "prompt_tokens", None),
        tokens_out=getattr(usage, "completion_tokens", None),
    )
    content = getattr(reply.choices[0].message, "content", None) or ""
    try:
        return schema.model_validate_json(content), result
    except (ValidationError, ValueError):
        log.warning("the agent model's reply did not fit the %s schema", schema_name)
        return None, result
