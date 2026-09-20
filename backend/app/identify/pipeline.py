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
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session_factory
from app.identify import early, qr
from app.identify import memory as memory_module
from app.identify.embed import Embedder, get_embedder, to_bytes
from app.identify.memory import DEFAULT_K, MemoryIndex, Neighbour, get_memory
from app.identify.openai_request import UNKNOWN_CHOICE
from app.identify.priors import MassPrior, fuse
from app.identify.providers import (
    CallUsage,
    EstimatorProvider,
    IdentifyContext,
    VisionProvider,
)
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
from app.schemas import (
    AskCandidate,
    PhoneAsk,
    PhoneIdle,
    UiAskOpened,
    UiAskResolved,
    VisionResult,
)

log = logging.getLogger(__name__)

MAX_ASK_CANDIDATES = 4
# A guess the model itself puts below this is not worth a button. PLAN.md 21a item 32.
ASK_CANDIDATE_FLOOR = 0.3
MAX_CONTEXT_LABELS = 60
MAX_CONTEXT_TAGS = 40
UNKNOWN_LABEL = "unknown object"
LOCAL_PROVIDER = "local"
# What the ask says when no model ever answered. A question with no answers in it and no
# reason given is the nonsense this wording exists to stop.
NO_CAMERA_ANSWER = "The camera answer did not arrive. What is it?"
# Who a ticket was settled by when the second call landed after the question went out.
CAMERA_ANSWERED = "camera"

# Watchers on second calls that were still out when the question went to a person.
_LATE_WATCHERS: set[asyncio.Task[None]] = set()

OnFinal = Callable[[int, str, ItemClass, IdentifyMethod], Awaitable[None]]


async def _no_op(_event_id: int, _label: str, _cls: ItemClass, _method: IdentifyMethod) -> None:
    """What happens on a final identification until the coordinator attaches the engine."""
    return None


# What the catalog says, wherever it lives -----------------------------------


# The key on `posterior_json` that says which branch decided. It carries an underscore, and
# a validated label cannot, so it can never collide with a real label in that map.
SAME_TREATMENT_KEY = "same_treatment"


@dataclass(frozen=True)
class Treatment:
    """Everything about a label that changes what the books do with it.

    PLAN.md 21a item 28. Two labels the model cannot tell apart are only a problem when
    they lead somewhere different. A usb cable against an hdmi cable is the same class, the
    same flag and the same material, so the entry, the tax and the carbon come out
    identical and the margin rule is asking a question with no consequence. A power bank
    against a portable speaker is not: one carries a battery flag and one does not.
    """

    item_class: ItemClass
    flags: frozenset[str]
    materials: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class CatalogFacts:
    labels: tuple[str, ...]
    classes: dict[str, ItemClass]
    priors: dict[str, MassPrior]
    treatments: dict[str, Treatment] = field(default_factory=dict)

    def same_treatment(self, one: str, other: str) -> bool:
        """True when the books cannot tell these two labels apart.

        A label the catalog does not carry has no known treatment, and an unknown is never
        the same as anything, including another unknown.
        """
        first = self.treatments.get(one)
        second = self.treatments.get(other)
        return first is not None and second is not None and first == second


def catalog_facts(session: Session) -> CatalogFacts:
    """Labels, classes and mass priors: the seed file, with the database rows over the top.

    A label a person taught the system is written to `catalog_item`, so the database is the
    newer of the two. It is never the whole catalog on its own, which is why the seed file
    is read first rather than only when the table is empty.
    """
    classes: dict[str, ItemClass] = {}
    priors: dict[str, MassPrior] = {}
    treatments: dict[str, Treatment] = {}
    try:
        from app.engine.records import load_catalog

        seed = load_catalog()
    except (OSError, KeyError, ValueError):
        log.warning("the catalog seed file is unreadable")
        seed = ()
    for item in seed:
        classes[item.label] = ItemClass(str(item.item_class))
        treatments[item.label] = _treatment(
            ItemClass(str(item.item_class)), item.regulatory_flags, item.material_mix
        )
        if item.mass_prior_mean_g is not None:
            priors[item.label] = MassPrior(
                mean_g=item.mass_prior_mean_g,
                var=item.mass_prior_var or 0.0,
                n=item.mass_prior_n,
            )
    for row in session.execute(select(CatalogItem).order_by(CatalogItem.label)).scalars():
        classes[row.label] = row.item_class
        treatments[row.label] = _treatment(
            row.item_class,
            _json_list(row.regulatory_flags_json),
            _json_map(row.material_mix_json),
        )
        if row.mass_prior_mean_g is not None:
            priors[row.label] = MassPrior(
                mean_g=row.mass_prior_mean_g,
                var=row.mass_prior_var or 0.0,
                n=row.mass_prior_n,
            )
        else:
            priors.pop(row.label, None)
    return CatalogFacts(tuple(sorted(classes)), classes, priors, treatments)


def _treatment(
    item_class: ItemClass, flags: Iterable[str], materials: Mapping[str, float]
) -> Treatment:
    return Treatment(
        item_class=item_class,
        flags=frozenset(str(flag) for flag in flags),
        materials=tuple(sorted((str(k), round(float(v), 4)) for k, v in materials.items())),
    )


def _json_list(raw: str | None) -> list[str]:
    try:
        loaded = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _json_map(raw: str | None) -> dict[str, float]:
    try:
        loaded = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): float(v) for k, v in loaded.items()}


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
    description: str = "",
) -> Identification:
    """One row per stage. This is the audit trail PLAN.md rule 4 asks for.

    `candidates_json` holds `{"candidates": [...], "description": "..."}` when the model
    said what it was looking at, and the bare list otherwise, which is what every row
    written before this change holds. `read_candidates` and `read_description` are the one
    place that difference is known about.
    """
    stored: Any = [{"label": name, "p": p} for name, p in candidates]
    if description:
        stored = {"candidates": stored, "description": description}
    row = Identification(
        event_id=event_id,
        method=method,
        label=label,
        item_class=item_class,
        confidence=confidence,
        candidates_json=json.dumps(stored),
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


# Words that make something food when the catalog has never heard of it. Short on purpose:
# a wrong guess here puts a toss through the wrong ledger account.
FOOD_WORDS = ("food", "snack", "fruit", "bread", "drink", "cup of", "slice", "edible")


def class_for(label: str, facts: CatalogFacts, description: str = "") -> ItemClass:
    """What this is, on the books, decided the same way every time.

    PLAN.md 21a item 51. The model was returning a class of its own and it flipped between
    identical crops, which moves a toss from inventory to untracked and changes which
    account it posts to. The catalog decides for anything it knows. Everything else is
    untracked, unless the words the model used about it are food words.
    """
    known = facts.classes.get(label)
    if known is not None:
        return known
    words = description.lower()
    if any(word in words for word in FOOD_WORDS):
        return ItemClass.inventory
    return ItemClass.untracked


def read_candidates(raw: object) -> list[dict[str, Any]]:
    """The candidate list out of a `candidates_json` value of either shape."""
    if isinstance(raw, dict):
        raw = raw.get("candidates")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and "label" in item]


# The key the sense gate's verdict is filed under, beside the numbers that produced it.
# It carries an underscore, and a validated label cannot, so it can never collide with one.
SENSE_CHECK_KEY = "sense_check"


def read_posterior(raw: object) -> dict[str, float]:
    """The numeric part of a `posterior_json` value.

    The map is a distribution over labels and the drawer draws it as one. Anything filed
    beside it that is not a number, which today is the sense gate's verdict, is read by its
    own name rather than let into the distribution.
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        out[str(key)] = float(value)
    return out


def read_sense_check(raw: object) -> dict[str, object] | None:
    """What the sense gate said about this ticket, when it was asked at all."""
    if not isinstance(raw, dict):
        return None
    found = raw.get(SENSE_CHECK_KEY)
    return dict(found) if isinstance(found, dict) else None


def read_description(raw: object) -> str | None:
    """What the model said it was looking at, when the row has it."""
    if isinstance(raw, dict):
        text = raw.get("description")
        if isinstance(text, str) and text:
            return text
    return None


def _confident_candidates(vision: VisionResult, floor: float = ASK_CANDIDATE_FLOOR
                          ) -> dict[str, float]:
    """The model's own guesses, and only the ones it meant.

    A candidate the model gave a one in ten chance is not a button worth drawing: it puts
    a wrong answer in front of a person as though the bin believed it.
    """
    return {str(c.label): float(c.p) for c in vision.candidates if c.p >= floor}


def top_two(distribution: dict[str, float]) -> tuple[tuple[str, float], tuple[str, float] | None]:
    ordered = sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ordered:
        return (UNKNOWN_LABEL, 0.0), None
    return ordered[0], (ordered[1] if len(ordered) > 1 else None)


def ask_candidates(distribution: dict[str, float]) -> list[AskCandidate]:
    """The buttons a person sees, best first. DESIGN.md section 4.4 draws up to four.

    An empty list is a real answer: the model had no guess worth showing, so the question
    is the picture, what the model says it is looking at, and Something else. A button
    reading "unknown object" was never an answer anybody could give.
    """
    ordered = sorted(distribution.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ASK_CANDIDATES]
    out: list[AskCandidate] = []
    for name, p in ordered:
        try:
            out.append(AskCandidate(label=name, p=max(0.0, min(1.0, p))))
        except ValueError:
            continue
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


def _neighbour_distances(neighbours: Sequence[Neighbour]) -> dict[str, float]:
    """The nearest distance per label, for the evidence drawer."""
    out: dict[str, float] = {}
    for neighbour in neighbours:
        best = out.get(neighbour.label)
        if best is None or neighbour.distance < best:
            out[neighbour.label] = round(neighbour.distance, 4)
    return out


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
    looks_like: str = "",
    question: str = "",
) -> list[AskCandidate]:
    """Set the event to asking and put the question on all three surfaces."""
    candidates = ask_candidates(distribution)
    event.status = EventStatus.asking
    session.flush()
    url = crop_url(event, deps.media_prefix)
    seen = looks_like or None
    asked = question or None
    deps.bus.publish(
        UiAskOpened(
            event_id=event.id,
            candidates=candidates,
            crop_url=url,
            looks_like=seen,
            question=asked,
        ),
        CHANNEL_UI,
    )
    deps.bus.publish(
        PhoneAsk(
            event_id=event.id,
            candidates=candidates,
            crop_url=url,
            looks_like=seen,
            question=asked,
        ),
        CHANNEL_PHONE,
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

    # Whatever the step-open hook started for this toss. Taking it here rather than at the
    # cloud stage means a QR tag or a remembered exemplar cancels it on the way out.
    pending = early.take(event_id)

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
                usage=_local_usage("qr-tag"),
                is_final=True,
            )
            return await _finalise(session, event, row, active, started)

        # 2. Memory. It no longer answers: it writes down who the neighbours are, and the
        # model is asked anyway. PLAN.md 21a item 23 and Lane K section 6. A crop that will
        # not decode simply skips this stage.
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
        if neighbours:
            write_identification(
                session,
                event_id=event_id,
                method=IdentifyMethod.memory,
                label=neighbours[0].label,
                item_class=facts.classes.get(neighbours[0].label, ItemClass.untracked),
                confidence=None,
                # A candidate's score is a probability, so the neighbours are listed by how
                # alike they are rather than how far away. The distances themselves are in
                # the posterior below, exactly as measured.
                candidates=[(n.label, max(0.0, min(1.0, 1.0 - n.distance))) for n in neighbours],
                # The drawer shows what memory had to say. These are cosine distances, not
                # probabilities: nearer is more like the crop, and nothing here decides.
                posterior=_neighbour_distances(neighbours),
                latency_ms=_elapsed(started),
                usage=_local_usage(active.embedder.name),
                is_final=False,
            )

        # 3. The cloud call, in a thread, under the timeout. Any failure goes to the ask.
        context = build_context(
            session,
            event_id=event_id,
            mass_g=mass_g,
            mass_err_g=mass_err_g,
            settings=settings,
        )
        vision, late = await _vision_answer(active, pending, event_id, crop, context)
        method = IdentifyMethod.stub if active.providers.name == "stub" else IdentifyMethod.cloud
        usage = getattr(active.providers.vision, "last_call", None)
        if vision is None:
            # Only what a remembered example says. The scale's own guesses used to fill
            # this in, which is how a battery came back offering "laptop charger, pencil,
            # power bank": three catalog rows that weigh about the same and nothing else.
            # Nothing came back, so there is nothing to offer. A remembered exemplar or
            # a catalog row that weighs about the same is not the model's guess, and
            # drawing it as a button says the bin believes something it does not.
            fallback: dict[str, float] = {}
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=None,
                item_class=None,
                confidence=None,
                posterior=fallback or None,
                latency_ms=_elapsed(started),
                usage=usage,
            )
            # Both goes are spent. The question says why it is being asked rather than
            # showing a person a bare "which is it" with nothing to pick.
            outcome = await _ask(
                session,
                event,
                fallback,
                active,
                started,
                row,
                question=NO_CAMERA_ANSWER,
            )
            if late is not None:
                _watch_late(late, event_id, method, active)
            return outcome

        vision_dist = _distribution(vision)
        if str(vision.label) == UNKNOWN_CHOICE:
            # The model is allowed to say it cannot tell, and that is a question for a
            # person rather than a label for the books. A label the catalog has never heard
            # of is not this: that is an untracked item and it goes through as one.
            log.info(
                "event %s: the model could not tell what it is (%s), so a person is asked",
                event_id,
                vision.description or "no description",
            )
            fallback = _confident_candidates(vision)
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=None,
                item_class=None,
                confidence=None,
                candidates=[(c.label, c.p) for c in vision.candidates],
                posterior=fallback or None,
                latency_ms=_elapsed(started),
                usage=usage,
                description=vision.description,
            )
            return await _ask(
                session, event, fallback, active, started, row, vision.description
            )

        raw_dist = dict(vision_dist)
        row = write_identification(
            session,
            event_id=event_id,
            method=method,
            label=vision.label,
            item_class=class_for(str(vision.label), facts, vision.description),
            confidence=vision.confidence,
            candidates=[(c.label, c.p) for c in vision.candidates],
            posterior=raw_dist,
            latency_ms=_elapsed(started),
            usage=usage,
            description=vision.description,
        )

        # 3b. Memory as a second opinion. Exemplars that back the model's answer raise its
        # confidence, so an ask stops being asked once a person has confirmed the same thing
        # a couple of times. Exemplars that disagree are a log line and nothing more.
        agreement = active.memory.agreement(neighbours, str(vision.label), settings)
        if agreement.agrees:
            vision_dist = memory_module.boost_label(
                vision_dist, agreement.label, len(agreement.agreeing)
            )
            log.info(
                "event %s: %d remembered example(s) agree with %s, nearest %.4f",
                event_id,
                len(agreement.agreeing),
                agreement.label,
                agreement.nearest or 0.0,
            )
        elif agreement.disagreeing:
            log.info(
                "event %s: memory's nearest example says %s and the model says %s, "
                "so memory is ignored",
                event_id,
                agreement.disagreeing[0].label,
                vision.label,
            )

        # 4. Mass prior fusion, but only when the scale has something to say about the
        # answer. PLAN.md 21a item 49: a label the catalog has never heard of has no prior,
        # so fusing pushed it down against catalog rows that merely weigh about the same,
        # and a battery the model named at 0.98 opened an ask. The scale judges the
        # catalog's own labels, and nothing else.
        final_dist = vision_dist
        top_label = str(vision.label)
        in_the_catalog = facts.priors.get(top_label, _NO_PRIOR).usable
        if in_the_catalog:
            # Fusion works on a normalised distribution, so the share the model left
            # unspoken for is put back afterwards rather than quietly filled in.
            claimed = min(sum(vision_dist.values()), 1.0)
            fused = fuse(vision_dist, mass_g, mass_err_g, facts.priors)
            # And never a label the model did not itself offer: the scale reweighs the
            # model's guesses, it does not add guesses of its own.
            final_dist = {
                label: p * claimed for label, p in fused.items() if label in vision_dist
            }
            best, _ = top_two(final_dist)
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=best[0],
                item_class=class_for(best[0], facts, vision.description),
                confidence=best[1],
                candidates=sorted(final_dist.items(), key=lambda kv: -kv[1])[:5],
                posterior=final_dist,
                used_mass_prior=True,
                latency_ms=_elapsed(started),
                usage=_local_usage("mass-prior-fusion"),
            )

        # 5. Decide. PLAN.md 21a item 28: by what it costs to be wrong, not by the margin
        # alone. Two labels that lead to the same entry, the same tax and the same carbon
        # are one answer as far as the books are concerned, and asking a person to pick
        # between them teaches the room that the bin cannot tell a cable from a cable.
        best, second = top_two(final_dist)
        margin = best[1] - (second[1] if second else 0.0)
        sure = best[1] >= settings.confident_p
        clear = margin >= settings.min_margin
        same_books = second is not None and facts.same_treatment(best[0], second[0])
        log.info(
            "event %s decided: label=%s p=%.2f margin=%.2f prior=%s treatment=%s -> %s",
            event_id,
            best[0],
            best[1],
            margin,
            "catalog" if in_the_catalog else "none",
            "same" if same_books else "differs",
            "accepted" if sure and (clear or same_books) else "asking",
        )
        if sure and (clear or same_books):
            row.is_final = True
            row.label = best[0]
            row.item_class = class_for(best[0], facts, vision.description)
            row.confidence = best[1]
            if not clear:
                # The drawer says "two candidates, same treatment" off this.
                row.posterior_json = json.dumps({**final_dist, SAME_TREATMENT_KEY: 1.0})
            session.flush()
            return await _finalise(session, event, row, active, started)
        return await _ask(
            session, event, final_dist, active, started, row, vision.description
        )
    finally:
        session.commit()
        session.close()
        if pending is not None:
            pending.cancel("the answer came from somewhere else")


_NO_PRIOR = MassPrior(mean_g=0.0, var=0.0, n=0)


def spend_on(session: Session, event_id: int) -> int:
    """Every microdollar this event's stages cost, added up.

    The round's cost used to be read off the last identification row, which was the row of
    the call that served the toss. Since the mass prior fusion writes a row of its own on
    top, and that stage runs here and costs nothing, reading the last row would report every
    cloud call as free. Adding the rows up is right whatever stages exist.
    """
    rows = session.execute(
        select(Identification.cost_microusd).where(Identification.event_id == event_id)
    ).scalars()
    return sum(int(value) for value in rows if value)


def _local_usage(model: str) -> CallUsage:
    """A stage that ran here. CLAUDE.md: every row says what served it, and this cost nothing."""
    return CallUsage(
        provider=LOCAL_PROVIDER, model=model, tokens_in=0, tokens_out=0,
        cost_microusd=0, price_known=True,
    )


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _asset_tags(session: Session) -> tuple[str, ...]:
    tags = session.execute(select(Asset.tag).order_by(Asset.tag)).scalars().all()
    return tuple(tags[:MAX_CONTEXT_TAGS])


def _distribution(vision: VisionResult) -> dict[str, float]:
    """The vision answer as a distribution over labels.

    Probability that adds up to less than one is left alone. The missing share is the
    model saying it might be none of these, and scaling it away would turn an unsure
    answer into a confident one, which is exactly the failure PLAN.md rule 3 forbids.
    """
    dist: dict[str, float] = {str(vision.label): float(vision.confidence)}
    for candidate in vision.candidates:
        name = str(candidate.label)
        dist[name] = max(dist.get(name, 0.0), float(candidate.p))
    total = sum(dist.values())
    return {label: p / total for label, p in dist.items()} if total > 1.0 else dist


def build_context(
    session: Session,
    *,
    event_id: int,
    mass_g: float | None,
    mass_err_g: float | None,
    settings: Settings,
    hints: dict[str, str] | None = None,
) -> IdentifyContext:
    """What a provider is allowed to know about one toss. Every field is code built."""
    facts = catalog_facts(session)
    return IdentifyContext(
        event_id=event_id,
        mass_g=float(mass_g or 0.0),
        mass_err_g=float(mass_err_g or 0.0),
        timeout_s=settings.llm_timeout_s,
        catalog_labels=facts.labels[:MAX_CONTEXT_LABELS],
        asset_tags=_asset_tags(session),
        hints=dict(hints or {}),
    )


def remember_vision(provider: object, event_id: int, vision: VisionResult) -> None:
    """Tell the glue's recorder what the model said, when the call had no event id yet.

    The early call runs before the event row exists, so it cannot key the answer by event.
    The second half of the pipeline reads the condition and the material off that record,
    so the answer is filed here instead. A provider with no recorder simply has no method.
    """
    keep = getattr(provider, "remember", None)
    if callable(keep):
        keep(event_id, vision)


async def _vision_answer(
    deps: IdentifyDeps,
    pending: early.Pending | None,
    event_id: int,
    crop: bytes | None,
    context: IdentifyContext,
) -> tuple[VisionResult | None, asyncio.Task[VisionResult] | None]:
    """The model's answer: the call that is already running, or a fresh one.

    The early call looks at a picture taken about 300 ms after the item landed, and the
    settled one looks at a later, better picture of the same thing. So an early answer is
    taken when it names something, and an early "unknown" is not an answer at all: it gets
    the settled crop its own call rather than opening an ask on the first frame anyone
    managed to grab. A tag has already been read off the settled frames before this runs,
    and beats both.
    """
    if pending is not None:
        answer, _looked_at = await pending.result(deps.settings.llm_timeout_s)
        if answer is not None and str(answer.label) != UNKNOWN_CHOICE:
            remember_vision(deps.providers.vision, event_id, answer)
            log.info(
                "event %s was answered by the call that started when the step opened",
                event_id,
            )
            return answer, None
        if answer is not None:
            log.info(
                "the early call for event %s could not name it, so the settled crop is "
                "asked about",
                event_id,
            )
        else:
            log.info("the early call for event %s gave nothing, asking now", event_id)
    return await _two_goes(deps, crop or b"", context)


async def _two_goes(
    deps: IdentifyDeps, crop: bytes, context: IdentifyContext
) -> tuple[VisionResult | None, asyncio.Task[VisionResult] | None]:
    """The settled call, and one more go when it does not come back in time.

    A live HP flash drive timed out at five seconds and the person was shown a question
    with no answers in it. The answer was coming; nothing was waiting for it. So a call
    that does not land gets a second go, thinking a little, with a longer budget, and the
    ask only opens when that one fails too. The second task is handed back rather than
    cancelled, because an answer that arrives late can still close the question.
    """
    answer = await _call_vision(deps, crop, context, deps.settings.llm_timeout_s)
    if answer is not None:
        return answer, None
    retry = replace(context, effort=deps.settings.vision_retry_effort)
    task: asyncio.Task[VisionResult] = asyncio.create_task(
        asyncio.to_thread(deps.providers.vision.identify, crop, retry)
    )
    try:
        again = await asyncio.wait_for(
            asyncio.shield(task), timeout=deps.settings.vision_retry_timeout_s
        )
    except TimeoutError:
        log.warning(
            "the second vision call for event %s is still out after %.0f s, so a person "
            "is asked and the answer is still waited for",
            context.event_id,
            deps.settings.vision_retry_timeout_s,
        )
        return None, task
    except Exception:
        log.exception("the second vision call for event %s failed", context.event_id)
        return None, None
    log.info("event %s was answered by the second vision call", context.event_id)
    return again, None


def _watch_late(
    task: asyncio.Task[VisionResult],
    event_id: int,
    method: IdentifyMethod,
    deps: IdentifyDeps,
) -> None:
    """Take a camera answer that arrives after the question went out, if nobody answered.

    A person who has already said what it is beats the camera every time, so this only
    does anything while the ticket is still waiting.
    """

    async def _settle() -> None:
        try:
            answer = await task
        except Exception:
            log.info("the late vision call for event %s never landed", event_id)
            return
        if answer is None or str(answer.label) == UNKNOWN_CHOICE:
            return
        session = deps.session_factory()
        try:
            event = session.get(Event, event_id)
            if event is None or event.status is not EventStatus.asking:
                log.info("event %s was already settled, so the late answer is dropped", event_id)
                return
            facts = catalog_facts(session)
            label = str(answer.label)
            remember_vision(deps.providers.vision, event_id, answer)
            row = write_identification(
                session,
                event_id=event_id,
                method=method,
                label=label,
                item_class=class_for(label, facts, answer.description),
                confidence=answer.confidence,
                candidates=[(c.label, c.p) for c in answer.candidates],
                posterior=_distribution(answer),
                usage=getattr(deps.providers.vision, "last_call", None),
                is_final=True,
                description=answer.description,
            )
            log.info("event %s was settled by a late camera answer: %s", event_id, label)
            deps.bus.publish(
                UiAskResolved(event_id=event_id, label=label, by=CAMERA_ANSWERED), CHANNEL_UI
            )
            deps.bus.publish(PhoneIdle(), CHANNEL_PHONE)
            await _finalise(session, event, row, deps, time.perf_counter())
        finally:
            session.commit()
            session.close()

    # Held so the loop cannot collect the task while it is still out.
    watcher = asyncio.create_task(_settle())
    _LATE_WATCHERS.add(watcher)
    watcher.add_done_callback(_LATE_WATCHERS.discard)


async def _call_vision(
    deps: IdentifyDeps, crop: bytes, context: IdentifyContext, timeout_s: float
) -> VisionResult | None:
    """Off the event loop, under the timeout, and never raising into ingest."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(deps.providers.vision.identify, crop, context),
            timeout=timeout_s,
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
        cost_microusd=spend_on(session, event.id),
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
    looks_like: str = "",
    question: str = "",
) -> Outcome:
    from app.learn import metrics, rounds

    candidates = open_ask(session, event, distribution, deps, looks_like, question)
    rounds.record_event(
        session,
        deps.settings,
        event=event,
        asked=True,
        confident=False,
        latency_ms=_elapsed(started),
        cost_microusd=spend_on(session, event.id),
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
    "SAME_TREATMENT_KEY",
    "SENSE_CHECK_KEY",
    "CatalogFacts",
    "IdentifyDeps",
    "Outcome",
    "Providers",
    "Treatment",
    "ask_candidates",
    "build_context",
    "build_providers",
    "catalog_facts",
    "class_for",
    "get_deps",
    "get_providers",
    "identify_event",
    "mass_fit_scores",
    "open_ask",
    "read_candidates",
    "read_description",
    "read_posterior",
    "read_sense_check",
    "remember_vision",
    "reset_identify",
    "reset_providers",
    "set_on_final",
    "spend_on",
    "store_exemplar",
    "top_two",
    "write_identification",
]
