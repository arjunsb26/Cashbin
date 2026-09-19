"""The OpenAI adapter: send, retry once, validate, record what it cost.

Request shape read off the installed SDK (openai 3.16.2): `chat.completions.create` with
`messages`, `model`, `response_format={"type":"json_schema",...}`, `reasoning_effort` and
`timeout`; an image is an `image_url` content part holding a data URL; token counts arrive
on `usage.prompt_tokens` and `usage.completion_tokens`. Chat completions rather than the
responses API, because LLM_BASE_URL is meant to point at a cheaper OpenAI-compatible host
and that is the endpoint they all implement.

The bodies themselves are built in `openai_request.py`, which is also where the rule about
outside text living in a data block is kept.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.identify.cost import cost_microusd, price_for
from app.identify.estimate_cache import read_estimate, write_estimate
from app.identify.openai_request import build_estimate_request, build_vision_request
from app.identify.providers import CallUsage, IdentifyContext
from app.schemas import ValueEstimate, VisionResult, normalise_label

log = logging.getLogger(__name__)

PROVIDER_NAME = "openai"
FALLBACK_CONFIDENCE = 0.3


class _Adapter:
    """Build, send, retry once on a reply that will not validate, record what it cost."""

    name = PROVIDER_NAME

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client
        self._memo: dict[str, ValueEstimate] = {}
        self.last_call: CallUsage | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            key, base_url = self.settings.openai_api_key, self.settings.llm_base_url
            self._client = OpenAI(api_key=key, base_url=base_url) if base_url else OpenAI(
                api_key=key
            )
        return self._client

    def _parse(self, request: dict[str, Any], model: str, shape: type[BaseModel]) -> Any:
        parsed: Any = None
        tokens: tuple[int | None, int | None] = (None, None)
        latency_ms: int | None = None
        for attempt in (1, 2):
            started = time.perf_counter()
            reply = self.client.chat.completions.create(
                **request, timeout=self.settings.llm_timeout_s
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            usage = getattr(reply, "usage", None)
            tokens = (getattr(usage, "prompt_tokens", None),
                      getattr(usage, "completion_tokens", None))
            try:
                parsed = shape.model_validate_json(reply.choices[0].message.content or "")
                break
            except (ValidationError, ValueError):
                log.warning("openai reply failed validation on attempt %d", attempt)
        price = price_for(model, PROVIDER_NAME)
        self.last_call = CallUsage(
            provider=PROVIDER_NAME, model=model, tokens_in=tokens[0], tokens_out=tokens[1],
            latency_ms=latency_ms, cost_microusd=cost_microusd(tokens[0], tokens[1], price),
            price_known=price is not None,
        )
        log.info("openai model=%s tokens_in=%s tokens_out=%s latency_ms=%s",
                 model, tokens[0], tokens[1], latency_ms)
        return parsed


class OpenAIVisionProvider(_Adapter):
    """Vision. A reply this code cannot read becomes a low-confidence answer, so the ask opens."""

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        model = self.settings.llm_vision_model
        request = build_vision_request(crop, context, model, self.settings.llm_vision_effort)
        parsed = self._parse(request, model, VisionResult)
        if parsed is None:
            return VisionResult.model_validate(
                {"label": "unknown object", "class": "untracked",
                 "confidence": FALLBACK_CONFIDENCE, "provider": PROVIDER_NAME, "model": model}
            )
        result: VisionResult = parsed
        return result.model_copy(update={"provider": PROVIDER_NAME, "model": model})


class OpenAIEstimatorProvider(_Adapter):
    """Value estimates, cached by normalised label so no object is ever priced twice."""

    def estimate(self, label: str, vision: VisionResult, mass_g: float) -> ValueEstimate:
        key = normalise_label(label)
        cached = self._memo.get(key) or read_estimate(key)
        if cached is not None:
            self._memo[key] = cached
            self.last_call = None
            return cached
        model, effort = self.settings.llm_text_model, self.settings.llm_text_effort
        parsed = self._parse(
            build_estimate_request(key, vision, mass_g, model, effort), model, ValueEstimate
        )
        if parsed is None:
            raise ValueError("the estimator returned nothing this code could read")
        estimate: ValueEstimate = parsed.model_copy(
            update={"label": key, "provider": PROVIDER_NAME, "model": model}
        )
        self._memo[key] = estimate
        write_estimate(key, estimate)
        return estimate
