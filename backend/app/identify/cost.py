"""What a model call cost, and what each call actually used.

Prices live in `backend/data/llm_prices.csv`, which Lane B owns. A row that still says
NEEDS_HUMAN, a model that is not listed, or a missing file all give no price, and the
identification row then stores `cost_microusd = None`. A missing price is never a zero:
zero would read as a free call on the cost chart, which is the one number that chart exists
to show.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.engine.records import LlmPrice, load_llm_prices
from app.identify.providers import CallUsage

__all__ = [
    "FAST_TIER_MULTIPLIER",
    "PREMIUM_TIERS",
    "CallUsage",
    "Price",
    "cost_microusd",
    "price_for",
]

log = logging.getLogger(__name__)

# The low latency queues are billed above the standard rate. The price table has one row per
# model and no tier column, so the multiplier lives here and is applied on top.
# https://developers.openai.com/api/docs/pricing
FAST_TIER_MULTIPLIER = 2.0
PREMIUM_TIERS: frozenset[str] = frozenset({"fast", "priority"})


@dataclass(frozen=True)
class Price:
    """Dollars per million tokens for one model."""

    provider: str
    model: str
    input_usd_per_million: float
    output_usd_per_million: float
    source: str | None = None


def _rows(path: Path | None = None) -> tuple[LlmPrice, ...]:
    try:
        return load_llm_prices(path)
    except (OSError, KeyError, ValueError):
        log.warning("llm price table unreadable, cost per call will be blank")
        return ()


def price_for(model: str, provider: str | None = None, path: Path | None = None) -> Price | None:
    """The price row for one model, or None when nobody has filled it in yet."""
    wanted = (model or "").strip()
    if not wanted:
        return None
    for row in _rows(path):
        if not row.complete or row.model != wanted:
            continue
        if provider and row.provider != provider:
            continue
        assert row.input_usd_per_million is not None
        assert row.output_usd_per_million is not None
        return Price(
            provider=row.provider,
            model=wanted,
            input_usd_per_million=row.input_usd_per_million,
            output_usd_per_million=row.output_usd_per_million,
            source=row.source,
        )
    return None


def cost_microusd(
    tokens_in: int | None,
    tokens_out: int | None,
    price: Price | None,
    service_tier: str = "",
) -> int | None:
    """Millionths of a dollar for one call, or None when the price is unknown.

    Dollars per million tokens times tokens is already microdollars, so there is no
    rounding step in the middle to lose.

    A call on the fast or priority queue is billed above the standard rate, so the cost
    chart has to know which queue served it. Without this every fast call read at about
    half what it really cost.
    """
    if price is None or tokens_in is None or tokens_out is None:
        return None
    total = tokens_in * price.input_usd_per_million + tokens_out * price.output_usd_per_million
    if service_tier.strip().lower() in PREMIUM_TIERS:
        total *= FAST_TIER_MULTIPLIER
    return round(total)
