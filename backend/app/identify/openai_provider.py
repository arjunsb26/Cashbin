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
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.detect.crop import downscale_jpeg
from app.engine.tax import round_money
from app.identify.cost import cost_microusd, price_for
from app.identify.estimate_cache import estimate_key, read_estimate, write_estimate
from app.identify.openai_request import (
    UNKNOWN_CHOICE,
    build_estimate_request,
    build_vision_request,
)
from app.identify.providers import CallUsage, IdentifyContext
from app.schemas import MoneyRange, ValueEstimate, VisionResult

log = logging.getLogger(__name__)

PROVIDER_NAME = "openai"
FALLBACK_CONFIDENCE = 0.3
# What a second go costs: a little thinking, on the same picture, once.
RETRY_EFFORT = "low"


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

    def _parse(
        self,
        request: dict[str, Any],
        model: str,
        shape: type[BaseModel],
        allowed: Callable[[Any], bool] | None = None,
    ) -> Any:
        parsed: Any = None
        tokens: tuple[int | None, int | None] = (None, None)
        cached: int | None = None
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
            cached = self._cached_tokens(usage)
            try:
                candidate = shape.model_validate_json(reply.choices[0].message.content or "")
            except (ValidationError, ValueError):
                log.warning("openai reply failed validation on attempt %d", attempt)
                continue
            if allowed is not None and not allowed(candidate):
                # The schema said which labels exist. A reply outside it is not an answer,
                # whatever the host thinks, so it is asked again and then given up on.
                log.warning("openai answered outside the catalog on attempt %d", attempt)
                parsed = None
                continue
            parsed = candidate
            break
        price = price_for(model, PROVIDER_NAME)
        tier = str(request.get("service_tier", ""))
        self.last_call = CallUsage(
            provider=PROVIDER_NAME, model=model, tokens_in=tokens[0], tokens_out=tokens[1],
            latency_ms=latency_ms,
            cost_microusd=cost_microusd(tokens[0], tokens[1], price, tier),
            price_known=price is not None,
            service_tier=tier or "default",
        )
        log.info(
            "openai model=%s tier=%s effort=%s tokens_in=%s cached_in=%s tokens_out=%s "
            "latency_ms=%s",
            model, request.get("service_tier", "default"), request.get("reasoning_effort"),
            tokens[0], cached, tokens[1], latency_ms,
        )
        return parsed

    @staticmethod
    def _cached_tokens(usage: Any) -> int | None:
        """How much of the prompt the host billed at the cached rate, when it says."""
        details = getattr(usage, "prompt_tokens_details", None)
        value = getattr(details, "cached_tokens", None)
        return int(value) if isinstance(value, int) else None


class OpenAIVisionProvider(_Adapter):
    """Vision. A reply this code cannot read becomes a low-confidence answer, so the ask opens."""

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        model = self.settings.llm_vision_model
        picture = downscale_jpeg(
            crop, self.settings.vision_image_max_px, self.settings.vision_image_quality
        )
        request = build_vision_request(
            picture,
            context,
            model,
            self.settings.llm_vision_effort,
            self.settings.llm_service_tier,
        )
        parsed = self._parse(request, model, VisionResult)
        parsed = self._retry_unknown(parsed, picture, context, model)
        if parsed is None:
            return VisionResult.model_validate(
                {"label": "unknown object", "class": "untracked",
                 "confidence": FALLBACK_CONFIDENCE, "provider": PROVIDER_NAME, "model": model}
            )
        result: VisionResult = parsed
        return result.model_copy(update={"provider": PROVIDER_NAME, "model": model})

    def _retry_unknown(
        self, parsed: Any, picture: bytes, context: IdentifyContext, model: str
    ) -> Any:
        """One more go, thinking a little, at something it described but would not name.

        PLAN.md 21a item 51. Lane R's bench: at effort `none` the model said "unknown" for
        a battery and then described it exactly; at effort `low` it named the battery, the
        pen and the flash drive every time. A reply that describes the thing has seen the
        thing, so the answer is in there and it is worth one cheap second to get it out.
        """
        if parsed is None:
            return None
        effort = self.settings.llm_vision_effort
        described = bool(getattr(parsed, "description", "").strip())
        if str(getattr(parsed, "label", "")) != UNKNOWN_CHOICE or not described:
            return parsed
        if effort == RETRY_EFFORT:
            return parsed
        log.info("the model described it but would not name it, retried at low")
        again = self._parse(
            build_vision_request(
                picture, context, model, RETRY_EFFORT, self.settings.llm_service_tier
            ),
            model,
            VisionResult,
        )
        if again is None or str(getattr(again, "label", "")) == UNKNOWN_CHOICE:
            return parsed
        return again


def clean_range(money: MoneyRange) -> MoneyRange:
    """One range with its mid cleaned to money a person would say out loud.

    PLAN.md 21a item 47, using the engine's own steps so the bin, the ticket and the books
    round the same way. Only the mid is cleaned; the low and the high keep every cent,
    because the drawer draws the range. The clamp is for narrow ranges: a mid of 9987 with
    a high of 9990 would otherwise round past its own high and fail validation.
    """
    mid = round_money(money.mid)
    if mid is None:
        return money
    return money.model_copy(
        update={"mid": mid, "low": min(money.low, mid), "high": max(money.high, mid)}
    )


def clean_estimate(estimate: ValueEstimate) -> ValueEstimate:
    """The four figures a person reads, cleaned before they leave the provider."""
    return estimate.model_copy(
        update={
            "fmv": clean_range(estimate.fmv),
            "repair": clean_range(estimate.repair),
            "replacement": clean_range(estimate.replacement),
            "scrap": clean_range(estimate.scrap),
        }
    )


class OpenAIEstimatorProvider(_Adapter):
    """Value estimates, cached by normalised label so no object is ever priced twice."""

    def estimate(self, label: str, vision: VisionResult, mass_g: float,
                 crop: bytes | None = None, detail: str = "") -> ValueEstimate:
        key = estimate_key(label, vision, detail)
        cached = self._memo.get(key) or read_estimate(key)
        if cached is not None:
            self._memo[key] = cached
            self.last_call = None
            return cached
        model = self.settings.llm_text_model
        # It is off the critical path since PLAN.md 21a item 25, and pricing a specific
        # product off a photograph is the one thing here worth thinking about.
        effort = self.settings.llm_estimate_effort
        picture = (
            downscale_jpeg(
                crop, self.settings.vision_image_max_px, self.settings.vision_image_quality
            )
            if crop
            else None
        )
        parsed = self._parse(
            build_estimate_request(
                key, vision, mass_g, model, effort, self.settings.llm_service_tier,
                picture, detail,
            ),
            model,
            ValueEstimate,
        )
        if parsed is None:
            raise ValueError("the estimator returned nothing this code could read")
        estimate: ValueEstimate = clean_estimate(
            parsed.model_copy(
                update={"label": key, "provider": PROVIDER_NAME, "model": model}
            )
        )
        self._memo[key] = estimate
        write_estimate(key, estimate)
        return estimate
