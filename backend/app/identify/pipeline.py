"""The identification pipeline: QR, memory, cloud, mass fusion, then a decision.

PLAN.md section 9. Each stage leaves an `identification` row behind, so the evidence drawer
can show what was tried, what it cost, and which provider and model actually served it.
Stopping early is the point: a QR tag or a remembered exemplar ends the run with no call at
all. When the answer is not good enough, nothing is guessed. The event goes to `asking` and
the three surfaces ask a person.

Nothing here raises out into ingest. A dead network, a timeout or a provider that returns
nonsense all land on the ask path, which is the graceful degradation PLAN.md rule 6 asks for.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.identify import qr
from app.identify.cost import CallUsage
from app.identify.embed import Embedder, get_embedder, to_bytes
from app.identify.memory import DEFAULT_K, MemoryIndex, Neighbour, get_memory
from app.identify.priors import MassPrior, fuse
from app.identify.providers import EstimatorProvider, IdentifyContext, VisionProvider
from app.identify.stub import StubEstimatorProvider, StubVisionProvider
from app.models import (
    Asset,
    CatalogItem,
    Event,
    EventStatus,
    Identification,
    IdentifyMethod,
    ItemClass,
)
from app.notify import lcd
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, CHANNEL_UI, Bus, get_bus
from app.schemas import AskCandidate, PhoneAsk, UiAskOpened, VisionResult

log = logging.getLogger(__name__)

MAX_ASK_CANDIDATES = 4
MAX_CONTEXT_LABELS = 60
MAX_CONTEXT_TAGS = 40
UNKNOWN_LABEL = "unknown object"

OnFinal = Callable[[int, str, ItemClass, IdentifyMethod], Awaitable[None]]


async def _no_op(_event_id: int, _label: str, _cls: ItemClass, _method: IdentifyMethod) -> None:
    """What happens on a final identification until the coordinator attaches the engine."""
    return None


# What the catalog says, wherever it lives -----------------------------------


@dataclass(frozen=True)
class CatalogFacts:
    labels: tuple[str, ...]
    classes: dict[str, ItemClass]
    priors: dict[str, MassPrior]


def catalog_facts(session: Session) -> CatalogFacts:
    """Labels, classes and mass priors, from the database, or from the seed file until seeded."""
    rows = list(session.execute(select(CatalogItem).order_by(CatalogItem.label)).scalars())
    labels: list[str] = []
    classes: dict[str, ItemClass] = {}
    priors: dict[str, MassPrior] = {}
    for row in rows:
        labels.append(row.label)
        classes[row.label] = row.item_class
        if row.mass_prior_mean_g is not None:
            priors[row.label] = MassPrior(
                mean_g=row.mass_prior_mean_g,
                var=row.mass_prior_var or 0.0,
                n=row.mass_prior_n,
            )
    if rows:
        return CatalogFacts(tuple(labels), classes, priors)
    try:
        from app.engine.records import load_catalog

        seed = load_catalog()
    except (OSError, KeyError, ValueError):
        log.warning("no catalog in the database and no readable seed file")
        return CatalogFacts((), {}, {})
    for item in seed:
        labels.append(item.label)
        classes[item.label] = ItemClass(str(item.item_class))
        if item.mass_prior_mean_g is not None:
            priors[item.label] = MassPrior(
                mean_g=item.mass_prior_mean_g,
                var=item.mass_prior_var or 0.0,
                n=item.mass_prior_n,
            )
    return CatalogFacts(tuple(labels), classes, priors)


# Providers ------------------------------------------------------------------


@dataclass(frozen=True)
class Providers:
    vision: VisionProvider
    estimator: EstimatorProvider
    name: str


def build_providers(settings: Settings) -> Providers:
    """Stub unless a provider and a key are both set. Today's behaviour is the default."""
    provider = settings.llm_provider.strip().lower()
    if provider == "openai" and settings.openai_api_key:
        from app.identify.openai_provider import (
            PROVIDER_NAME,
            OpenAIEstimatorProvider,
            OpenAIVisionProvider,
        )

        return Providers(
            vision=OpenAIVisionProvider(settings),
            estimator=OpenAIEstimatorProvider(settings),
            name=PROVIDER_NAME,
        )
    if provider and provider != "openai":
        log.warning("unknown llm provider in settings, using the stub instead")
    return Providers(vision=StubVisionProvider(), estimator=StubEstimatorProvider(), name="stub")


# Dependencies ---------------------------------------------------------------


@dataclass
class IdentifyDeps:
    """Everything the pipeline touches, passed in so a test can replace any one piece."""

    session_factory: Callable[[], Session]
    providers: Providers
    embedder: Embedder
    memory: MemoryIndex
    settings: Settings
    bus: Bus
    on_final: OnFinal = _no_op
    media_prefix: str = "/media"


@dataclass(frozen=True)
class Outcome:
    final: bool
    label: str | None = None
    item_class: ItemClass | None = None
    method: IdentifyMethod | None = None
    confidence: float | None = None
    identification_id: int | None = None
    candidates: tuple[AskCandidate, ...] = ()


_on_final: OnFinal = _no_op
_providers: Providers | None = None
_providers_for: tuple[str, str, str, str, bool] | None = None


def _provider_key(settings: Settings) -> tuple[str, str, str, str, bool]:
    """What a provider is built from. Change any of it and the providers are rebuilt."""
    return (
        settings.llm_provider,
        settings.llm_base_url,
        settings.llm_vision_model,
        settings.llm_text_model,
        bool(settings.openai_api_key),
    )


def set_on_final(callback: OnFinal) -> None:
    """The glue attaches the engine and the ledger here. Called once at startup."""
    global _on_final
    _on_final = callback


def get_providers(settings: Settings) -> Providers:
    """One set of providers per configuration, so the estimator cache survives between events."""
    global _providers, _providers_for
    key = _provider_key(settings)
    if _providers is None or _providers_for != key:
        _providers = build_providers(settings)
        _providers_for = key
    return _providers


def get_deps(settings: Settings | None = None) -> IdentifyDeps:
    """The process-wide dependencies. Routes and ingest both come through here."""
    active = settings or get_settings()
    return IdentifyDeps(
        session_factory=get_session_factory(),
        providers=get_providers(active),
        embedder=get_embedder(),
        memory=get_memory(),
        settings=active,
        bus=get_bus(),
        on_final=_on_final,
    )


def reset_providers() -> None:
    """Drop the cached providers. Tests and a settings swap call this."""
    global _providers, _providers_for
    _providers = None
    _providers_for = None


def reset_identify() -> None:
    """Forget the providers, the memory index and anything the simulator queued.

    Everything identification holds between events lives in three process globals. A test,
    or a database swap, starts from nothing by calling this.
    """
    from app.identify.memory import reset_memory
    from app.identify.stub import reset_expect_queue

    reset_providers()
    reset_memory()
    reset_expect_queue()


# Rows and messages ----------------------------------------------------------


def write_identification(
    session: Session,
    *,
    event_id: int,
    method: IdentifyMethod,
    label: str | None,
    item_class: ItemClass | None,
    confidence: float | None,
    candidates: Sequence[tuple[str, float]] = (),
    posterior: dict[str, float] | None = None,
    used_mass_prior: bool = False,
    latency_ms: int | None = None,
    usage: CallUsage | None = None,
    is_final: bool = False,
) -> Identification:
    """One row per stage. This is the audit trail PLAN.md rule 4 asks for."""
    row = Identification(
        event_id=event_id,
        method=method,
        label=label,
        item_class=item_class,
        confidence=confidence,
        candidates_json=json.dumps([{"label": name, "p": p} for name, p in candidates]),
        posterior_json=json.dumps(posterior) if posterior else None,
        used_mass_prior=used_mass_prior,
        latency_ms=latency_ms,
        cost_microusd=usage.cost_microusd if usage else None,
        tokens_in=usage.tokens_in if usage else None,
        tokens_out=usage.tokens_out if usage else None,
        is_final=is_final,
        provider=usage.provider if usage else None,
        model=usage.model if usage else None,
    )
    session.add(row)
    session.flush()
    return row


def top_two(distribution: dict[str, float]) -> tuple[tuple[str, float], tuple[str, float] | None]:
    ordered = sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ordered:
        return (UNKNOWN_LABEL, 0.0), None
    return ordered[0], (ordered[1] if len(ordered) > 1 else None)


def ask_candidates(distribution: dict[str, float]) -> list[AskCandidate]:
    """The buttons a person sees, best first. DESIGN.md section 4.4 draws two to four."""
    ordered = sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ASK_CANDIDATES]
    out: list[AskCandidate] = []
    for name, p in ordered:
        try:
            out.append(AskCandidate(label=name, p=max(0.0, min(1.0, p))))
        except ValueError:
            continue
    if not out:
        out.append(AskCandidate(label=UNKNOWN_LABEL, p=0.0))
    return out


def crop_url(event: Event, prefix: str) -> str | None:
    if not event.crop:
        return None
    return event.crop if event.crop.startswith(("/", "http")) else f"{prefix}/{event.crop}"


def _mass_fit(facts: CatalogFacts, mass_g: float | None, mass_err_g: float | None
              ) -> dict[str, float]:
    """Which catalog labels the scale alone would allow. Used when there is nothing else."""
    usable = {label: prior for label, prior in facts.priors.items() if prior.usable}
    if not usable or mass_g is None:
        return {}
    err = float(mass_err_g or 0.0)
    flat = dict.fromkeys(usable, 1.0)
    return fuse(flat, mass_g, err, usable)


def _neighbour_votes(neighbours: Sequence[Neighbour]) -> dict[str, float]:
    if not neighbours:
        return {}
    counts: dict[str, float] = {}
    for neighbour in neighbours:
        counts[neighbour.label] = counts.get(neighbour.label, 0.0) + 1.0
    return {label: votes / len(neighbours) for label, votes in counts.items()}


def open_ask(
    session: Session,
    event: Event,
    distribution: dict[str, float],
    deps: IdentifyDeps,
) -> list[AskCandidate]:
    """Set the event to asking and put the question on all three surfaces."""
    candidates = ask_candidates(distribution)
    event.status = EventStatus.asking
    session.flush()
    url = crop_url(event, deps.media_prefix)
    deps.bus.publish(
        UiAskOpened(event_id=event.id, candidates=candidates, crop_url=url), CHANNEL_UI
    )
    deps.bus.publish(
        PhoneAsk(event_id=event.id, candidates=candidates, crop_url=url), CHANNEL_PHONE
    )
    deps.bus.publish(lcd.ask(), CHANNEL_BIN)
    return candidates


# The pipeline ---------------------------------------------------------------


async def identify_event(
    event_id: int,
    crop: bytes | None,
    frames: Sequence[bytes],
    mass_g: float | None,
    mass_err_g: float | None,
    deps: IdentifyDeps | None = None,
) -> Outcome:
    """Identify one toss. Returns final with a label, or not final with the ask opened."""
    active = deps or get_deps()
    settings = active.settings
    active.bus.publish(lcd.thinking(), CHANNEL_BIN)
    started = time.perf_counter()

    session = active.session_factory()
    try:
        event = session.get(Event, event_id)
        if event is None:
            raise ValueError(f"event {event_id} does not exist")
        facts = catalog_facts(session)

        # 1. QR asset tag. Exact match, confidence 1.0, no call and no cost.
        tags = qr.read_tags(frames)
        asset = qr.match_asset(tags, session) if tags else None
        if asset is not None:
            row = write_identification(
                session,
                event_id=event_id,
                method=IdentifyMethod.qr,
                label=asset.tag,
                item_class=ItemClass.fixed_asset,
                confidence=1.0,
                candidates=[(asset.tag, 1.0)],
                posterior={asset.tag: 1.0},
                latency_ms=_elapsed(started),
                is_final=True,
            )
            return await _finalise(session, event, row, active, started)

        # 2. Memory. A crop that will not decode simply skips this stage.
        neighbours: list[Neighbour] = []
        vector = None
        if crop:
            try:
                vector = active.embedder.embed(crop)
            except ValueError:
                log.warning("crop for event %s did not decode", event_id)
        if vector is not None:
            active.memory.ensure_loaded(session)
            neighbours = active.memory.query(vector, DEFAULT_K)
            hit = active.memory.decide(neighbours, settings)
            if hit is not None:
                votes = _neighbour_votes(hit.neighbours)
                row = write_identification(
                    session,
                    event_id=event_id,
                    method=IdentifyMethod.memory,
                    label=hit.label,
                    item_class=facts.classes.get(hit.label, ItemClass.untracked),
                    confidence=hit.confidence,
                    candidates=sorted(votes.items(), key=lambda kv: -kv[1]),
                    posterior=votes,
                    latency_ms=_elapsed(started),
                    is_final=True,
                )
                return await _finalise(session, event, row, active, started)

        # 3. The cloud call, in a thread, under the timeout. Any failure goes to the ask.
        context = IdentifyContext(
            event_id=event_id,
            mass_g=float(mass_g or 0.0),
            mass_err_g=float(mass_err_g or 0.0),
            timeout_s=settings.llm_timeout_s,
            catalog_labels=facts.labels[:MAX_CONTEXT_LABELS],
            asset_tags=_asset_tags(session),
        )
        vision = await _call_vision(active, crop or b"", context)
        method = IdentifyMethod.stub if active.providers.name == "stub" else IdentifyMethod.cloud
        usage = getattr(active.providers.vision, "last_call", None)
        if vision is None:
            fallback = _neighbour_votes(neighbours) or _mass_fit(facts, mass_g, mass_err_g)
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=None,
                item_class=None,
                confidence=None,
                posterior=fallback or None,
                used_mass_prior=bool(fallback and not neighbours),
                latency_ms=_elapsed(started),
                usage=usage,
            )
            return await _ask(session, event, fallback, active, started, row)

        vision_dist = _distribution(vision)
        row = write_identification(
            session,
            event_id=event_id,
            method=method,
            label=vision.label,
            item_class=vision.item_class,
            confidence=vision.confidence,
            candidates=[(c.label, c.p) for c in vision.candidates],
            posterior=vision_dist,
            latency_ms=_elapsed(started),
            usage=usage,
        )

        # 4. Mass prior fusion, when a prior has enough weighings behind it to count.
        final_dist = vision_dist
        if any(facts.priors.get(label, _NO_PRIOR).usable for label in vision_dist):
            final_dist = fuse(vision_dist, mass_g, mass_err_g, facts.priors)
            best, _ = top_two(final_dist)
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=best[0],
                item_class=facts.classes.get(best[0], vision.item_class),
                confidence=best[1],
                candidates=sorted(final_dist.items(), key=lambda kv: -kv[1])[:5],
                posterior=final_dist,
                used_mass_prior=True,
                latency_ms=_elapsed(started),
            )

        # 5. Decide.
        best, second = top_two(final_dist)
        margin = best[1] - (second[1] if second else 0.0)
        if best[1] >= settings.confident_p and margin >= settings.min_margin:
            row.is_final = True
            row.label = best[0]
            row.item_class = facts.classes.get(best[0], vision.item_class)
            row.confidence = best[1]
            session.flush()
            return await _finalise(session, event, row, active, started)
        return await _ask(session, event, final_dist, active, started, row)
    finally:
        session.commit()
        session.close()


_NO_PRIOR = MassPrior(mean_g=0.0, var=0.0, n=0)


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _asset_tags(session: Session) -> tuple[str, ...]:
    tags = session.execute(select(Asset.tag).order_by(Asset.tag)).scalars().all()
    return tuple(tags[:MAX_CONTEXT_TAGS])


def _distribution(vision: VisionResult) -> dict[str, float]:
    """The vision answer as a distribution over labels, normalised."""
    dist: dict[str, float] = {str(vision.label): float(vision.confidence)}
    for candidate in vision.candidates:
        name = str(candidate.label)
        dist[name] = max(dist.get(name, 0.0), float(candidate.p))
    total = sum(dist.values())
    return {label: p / total for label, p in dist.items()} if total > 0 else dist


async def _call_vision(
    deps: IdentifyDeps, crop: bytes, context: IdentifyContext
) -> VisionResult | None:
    """Off the event loop, under the timeout, and never raising into ingest."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(deps.providers.vision.identify, crop, context),
            timeout=deps.settings.llm_timeout_s,
        )
    except TimeoutError:
        log.warning("vision call for event %s timed out", context.event_id)
    except Exception:
        log.exception("vision call for event %s failed", context.event_id)
    return None


async def _finalise(
    session: Session,
    event: Event,
    row: Identification,
    deps: IdentifyDeps,
    started: float,
) -> Outcome:
    from app.learn import metrics, rounds

    event.status = EventStatus.identified
    label = row.label or UNKNOWN_LABEL
    item_class = row.item_class or ItemClass.untracked
    rounds.record_event(
        session,
        deps.settings,
        event=event,
        asked=False,
        confident=True,
        latency_ms=_elapsed(started),
        cost_microusd=row.cost_microusd,
    )
    session.commit()
    metrics.publish_metrics(session, deps.bus)
    await deps.on_final(event.id, label, item_class, row.method)
    return Outcome(
        final=True,
        label=label,
        item_class=item_class,
        method=row.method,
        confidence=row.confidence,
        identification_id=row.id,
    )


async def _ask(
    session: Session,
    event: Event,
    distribution: dict[str, float],
    deps: IdentifyDeps,
    started: float,
    row: Identification,
) -> Outcome:
    from app.learn import metrics, rounds

    candidates = open_ask(session, event, distribution, deps)
    rounds.record_event(
        session,
        deps.settings,
        event=event,
        asked=True,
        confident=False,
        latency_ms=_elapsed(started),
        cost_microusd=row.cost_microusd,
    )
    session.commit()
    metrics.publish_metrics(session, deps.bus)
    return Outcome(
        final=False,
        method=row.method,
        identification_id=row.id,
        candidates=tuple(candidates),
    )


def store_exemplar(
    session: Session,
    deps: IdentifyDeps,
    *,
    event: Event,
    label: str,
    crop: bytes,
    confirmed_by: str,
) -> int | None:
    """Turn a person's answer into an exemplar, so the next toss is recognised for free."""
    from app.models import Exemplar

    try:
        vector = deps.embedder.embed(crop)
    except ValueError:
        log.warning("crop for event %s did not decode, no exemplar stored", event.id)
        return None
    row = Exemplar(
        event_id=event.id,
        label=label,
        embedding=to_bytes(vector),
        mass_g=event.mass_g,
        confirmed_by=confirmed_by,
    )
    session.add(row)
    session.flush()
    deps.memory.ensure_loaded(session)
    deps.memory.add(row)
    return row.id


def mass_fit_scores(
    facts: CatalogFacts, mass_g: float | None, mass_err_g: float | None
) -> dict[str, float]:
    """Exposed for the evidence drawer: what the scale alone says about each catalog label."""
    return _mass_fit(facts, mass_g, mass_err_g)


__all__ = [
    "CatalogFacts",
    "IdentifyDeps",
    "Outcome",
    "Providers",
    "ask_candidates",
    "build_providers",
    "catalog_facts",
    "get_deps",
    "get_providers",
    "identify_event",
    "mass_fit_scores",
    "open_ask",
    "reset_identify",
    "reset_providers",
    "set_on_final",
    "store_exemplar",
    "top_two",
    "write_identification",
]
