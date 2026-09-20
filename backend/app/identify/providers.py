"""Provider interfaces from PLAN.md section 9. Step 0 owns this file. Lane C writes the providers.

Nothing here has an implementation on purpose. A provider is anything that satisfies the
Protocol, so the stub and the real adapter can live side by side and swap by config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.schemas import ValueEstimate, VisionResult


@dataclass(frozen=True)
class CallUsage:
    """What one provider call used, read off the provider after it answers.

    CLAUDE.md: every identification and estimate row carries which provider and model
    actually served it, and what the call cost. A VisionResult has no room for tokens or
    latency, so a provider records them here and the pipeline copies them onto the row.
    A count nobody measured stays None. A price nobody has filled in gives no cost at all,
    never a zero, because a zero reads as a free call on the cost chart.
    """

    provider: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    cost_microusd: int | None = None
    price_known: bool = False
    # Which queue the host was asked to use. The fast queue is billed above the standard
    # rate, so a cost figure without this cannot be checked.
    service_tier: str = ""


@dataclass(frozen=True)
class IdentifyContext:
    """What a provider is allowed to know about the toss it is looking at.

    Every field is code-built data. Nothing a person typed reaches a provider as instructions.
    """

    event_id: int
    mass_g: float
    mass_err_g: float
    timeout_s: float
    catalog_labels: tuple[str, ...] = ()
    asset_tags: tuple[str, ...] = ()
    hints: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class VisionProvider(Protocol):
    """Identify an item from its crop."""

    name: str
    last_call: CallUsage | None

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult: ...


@runtime_checkable
class EstimatorProvider(Protocol):
    """Estimate fair market value, repair, replacement and scrap for an unknown object."""

    name: str
    last_call: CallUsage | None

    def estimate(self, label: str, vision: VisionResult, mass_g: float,
                 crop: bytes | None = None, detail: str = "") -> ValueEstimate:
        """Price one object. `crop` is the same picture the vision call saw and `detail` is
        the answer to the bin's question; both are optional and both make the price better.
        PLAN.md 21a item 29."""
        ...
