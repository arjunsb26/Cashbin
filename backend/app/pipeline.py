"""One toss, all the way through: identify it, price it, post it, then say so.

Every lane left a seam and stopped. Ingest calls `on_event` and knows nothing about
identification. Identification calls `on_final` and knows nothing about money. The engine
and the ledger are pure functions that never touch a session. This module is the only place
those halves meet, so the wiring is readable in one file and no lane had to import another.

What happens to a settled step, in order:

1. `on_event` hands the crop and the frames to `identify_event`.
2. `identify_event` decides, or asks a person, and calls `on_final` when it is sure.
3. `finalise_event` loads the catalog row or the register row, builds the item record,
   scores every fate it could have had, writes both tables, posts the journal entries,
   takes the asset off the register, and puts the answer on the LCD, the phone and the
   dashboard.

Nothing here raises into a socket. A stage that fails is logged with its name and the event
keeps the last status it honestly earned, because a half-posted ticket that claims to be
posted is worse than one that stops and says where it stopped.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models
from app.agent import sense_check
from app.api.assets import to_asset_info
from app.api.events import _summary as event_summary
from app.config import Settings
from app.detect.crop import CropParams, Frame, FramePick, crop_item, pick_frames
from app.detect.steps import Step
from app.engine import options as engine_options
from app.engine import records as engine_records
from app.engine.records import (
    AssetInfo,
    CatalogItem,
    Condition,
    EngineSettings,
    Estimate,
    EstimateSource,
    ItemClass,
    ItemRecord,
    Option,
    OptionScore,
)
from app.engine.tax import money, round_money, tax_effect_for
from app.identify import early, estimate_cache, qr
from app.identify.embed import Embedder, get_embedder
from app.identify.memory import MemoryIndex, get_memory
from app.identify.pipeline import (
    DETAIL_CONDITION_KEY,
    DETAIL_KEY,
    SENSE_CHECK_KEY,
    IdentifyDeps,
    Providers,
    build_context,
    build_providers,
    identify_event,
    open_ask,
    read_answers,
    set_on_final,
)
from app.identify.providers import CallUsage, IdentifyContext, VisionProvider
from app.ingest.media import read_jpeg
from app.ingest.state import IngestState
from app.learn import metrics, rounds
from app.ledger import journal as ledger_journal
from app.ledger import queries as ledger_queries
from app.notify import lcd
from app.notify.bus import CHANNEL_BIN, CHANNEL_PHONE, CHANNEL_UI, Bus, get_bus
from app.schemas import (
    LCD_BIG_MAX,
    LcdColour,
    PhoneResult,
    UiEventUpdated,
    UiJournalPosted,
    ValueEstimate,
    VisionResult,
)

log = logging.getLogger(__name__)

# How many events' vision answers to keep. One per open ask plus slack; the ask path is the
# only reason a result has to wait longer than the toss it belongs to.
VISION_KEEP = 64

TONES: dict[str, LcdColour] = {"green": "green", "amber": "amber", "red": "red"}

# User copy. DESIGN.md section 8: say what to do, or say what happened, in one short line.
BLOCKED_ONLY = "Not for the bin"
# What the bin says when it has nothing to argue about, which is most of the time.
FINE_TO_BIN = "Fine to bin"
ADVICE: dict[Option, str] = {
    Option.recycle: "Recycle it instead",
    Option.donate: "Donate it instead",
    Option.resell: "Resell it instead",
    Option.repair: "Repair it instead",
}
# PLAN.md 21a item 31. "No bin. Repair it" read as a bug to the first person who used it:
# two sentences, the first one a refusal, and nothing saying what the bin was refusing.
# Saying what to do and what not to do in one clause fixes it, inside the 20 columns.
BLOCKED_ADVICE: dict[Option, str] = {
    Option.recycle: "Recycle, not trash",
    Option.donate: "Donate it, not trash",
    Option.resell: "Resell it, not trash",
    Option.repair: "Repair it, not trash",
}
# User copy, for the moment between knowing what a thing is and knowing what it is worth.
VALUING_BIG = "..."
VALUING_LINE = "Working out value"

BINNED: dict[ItemClass, str] = {
    ItemClass.fixed_asset: "Removed from books",
    ItemClass.inventory: "Written off as waste",
    ItemClass.untracked: "Nothing on the books",
}


# Money and copy, one source for all three surfaces ---------------------------


def signed_money(cents: int) -> str:
    """Accounting money with its sign, from the same formatter the engine's notes use."""
    sign = "-" if cents < 0 else ""
    return f"{sign}${money(abs(cents))}"


def lcd_big(cents: int) -> str:
    """The same figure, cut down until the bin can draw it. Cents go first, then commas."""
    full = signed_money(cents)
    if len(full) <= LCD_BIG_MAX:
        return full
    sign = "-" if cents < 0 else ""
    whole = f"{sign}${abs(cents) // 100:,}"
    if len(whole) <= LCD_BIG_MAX:
        return whole
    plain = whole.replace(",", "")
    if len(plain) <= LCD_BIG_MAX:
        return plain
    # Past six figures the bin rounds to thousands. The exact figure is on the ticket.
    return f"{sign}${round(abs(cents) / 100_000)}k"


def headline_cents(record: ItemRecord) -> int:
    """The one figure the ticket, the phone and the LCD lead with.

    A fixed asset leads with the book loss, inventory with the waste expense, and an
    untracked object with what it would fetch. The dashboard captions the three the same
    way, so the number under the caption is the number every surface shows.
    """
    if record.item_class is ItemClass.fixed_asset:
        return -record.book_value_cents
    if record.item_class is ItemClass.inventory:
        return -(record.cost_basis_cents or 0)
    return record.fmv_mid or 0


# Words nobody writes in lower case. "Usb-c charger" was what the bin drew before this, and
# a judge reading it sees a bug rather than a charger. Keep it to what the catalog holds.
ACRONYMS = frozenset({"usb", "usb-c", "hdmi", "led", "lcd", "sd", "hd"})


def title_for(label: str) -> str:
    """The label as a person reads it. Labels are stored lowercase; sentences are not."""
    words = label.split(" ")
    shown = [word.upper() if word.lower() in ACRONYMS else word for word in words]
    joined = " ".join(shown)
    return joined[:1].upper() + joined[1:]


def advice_line(
    record: ItemRecord,
    ranking: engine_options.Ranking,
    blocked: bool,
    speak_up_cents: int = 100,
) -> str:
    """One line: what to do instead, or that the bin was the right place for it.

    PLAN.md 21a item 37. The user's words: if something is trash you should just say it is
    trash. A bin that says "Donate it instead" to save three cents on a bagel is a bin
    nobody believes the fourth time, so it only speaks up when the difference is worth
    hearing, or when the bin is not allowed to have the thing at all.
    """
    best = ranking.best_option
    if blocked:
        if best is not None and best in BLOCKED_ADVICE:
            return BLOCKED_ADVICE[best]
        return BLOCKED_ONLY
    if (
        best is not None
        and best is not Option.trash
        and best in BLOCKED_ADVICE
        and ranking.saved_if_followed_cents >= speak_up_cents
    ):
        return BLOCKED_ADVICE[best]
    if record.item_class is ItemClass.fixed_asset:
        # A tagged asset leaving the register is the news on that ticket, and it is worth
        # more than telling somebody the bin was an acceptable place for it.
        return BINNED[ItemClass.fixed_asset]
    return FINE_TO_BIN


# Small conversions between the database rows and the engine's own types ------


def _event_date(event: models.Event) -> date:
    """The day this toss happened, from the row's own stamp."""
    try:
        return datetime.fromisoformat(event.created_at.replace("Z", "+00:00")).date()
    except ValueError:
        log.warning("event %s has an unreadable timestamp, using today", event.id)
        return datetime.now(UTC).date()


def _loads(raw: str | None, fallback: object) -> object:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def to_catalog_item(row: models.CatalogItem) -> CatalogItem:
    """A catalog row as the engine's own type. The two JSON columns become real fields."""
    mix = _loads(row.material_mix_json, {})
    flags = _loads(row.regulatory_flags_json, [])
    return CatalogItem.model_validate(
        {
            "id": int(row.id),
            "label": row.label,
            "class": ItemClass(row.item_class.value),
            "unit_cost_cents": row.unit_cost_cents,
            "unit_mass_g": row.unit_mass_g,
            "price_per_kg_cents": row.price_per_kg_cents,
            "fmv_per_kg_cents": row.fmv_per_kg_cents,
            "material_mix": mix if isinstance(mix, dict) else {},
            "regulatory_flags": flags if isinstance(flags, list) else [],
            "mass_prior_mean_g": row.mass_prior_mean_g,
            "mass_prior_var": row.mass_prior_var,
            "mass_prior_n": row.mass_prior_n,
        }
    )


@dataclass(frozen=True)
class _Pricing:
    """Everything a pricing pass needs that does not change between the two passes."""

    event_id: int
    label: str
    cls: ItemClass
    mass_g: float
    when: date
    catalog: CatalogItem | None
    asset: AssetInfo | None
    asset_row: models.Asset | None
    condition: Condition
    # What the camera said it was looking at, and what a person answered about it. Both
    # are outside text, both are data, and the engine reads them for words like "sealed".
    description: str = ""
    detail: str = ""


@dataclass(frozen=True)
class _Words:
    """What the three surfaces draw for one ticket. One source, three surfaces."""

    title: str
    line: str
    tone: LcdColour
    big: str
    lcd_money: str
    blocked: bool
    best_option: Option | None

    def rewritten(self, checked: sense_check.SenseCheck) -> _Words:
        """The same ticket in the sense gate's words, with the option it named."""
        best = self.best_option
        if checked.best_option:
            try:
                best = Option(checked.best_option)
            except ValueError:
                best = self.best_option
        return _Words(
            title=self.title,
            line=checked.line2,
            tone=self.tone,
            big=self.big,
            lcd_money=self.lcd_money,
            blocked=self.blocked,
            best_option=best,
        )


def _store_sense(session: Session, event_id: int, checked: sense_check.SenseCheck) -> None:
    """File the verdict on the identification row this ticket was decided by.

    The evidence drawer reads `posterior_json`, so the verdict lands beside the numbers
    that produced it rather than in a table of its own.
    """
    row = session.scalars(
        select(models.Identification)
        .where(models.Identification.event_id == event_id)
        .order_by(models.Identification.id.desc())
    ).first()
    if row is None:
        return
    posterior = _loads(row.posterior_json, {})
    if not isinstance(posterior, dict):
        posterior = {}
    posterior[SENSE_CHECK_KEY] = checked.model_dump(exclude={"latency_ms"})
    row.posterior_json = json.dumps(posterior)
    session.flush()


def _early_frames(frames: Sequence[Frame], opened_ms: float) -> list[bytes]:
    """The frames a tag could be read off at this point: the newest ones since the open.

    `frame_bytes` reads the after and the peak frame of a settled step. There is no settled
    step yet, so this takes the newest frames instead, which is where the item just landed.
    """
    recent = sorted((f for f in frames if f.t_ms >= opened_ms), key=lambda f: -f.t_ms)
    return [frame.jpeg for frame in recent[:2] if frame.jpeg]


def _early_crop(frames: Sequence[Frame], opened_ms: float, at_ms: float) -> bytes | None:
    """Cut the new thing out of the picture taken a moment after the step opened.

    `pick_frames` works off a step, and at this point there is no step: the detector will
    not know whether this was a toss for another second. A stand-in carrying the two stamps
    it reads is enough, and keeps one frame picking rule for the early call and the real one.
    """
    if not frames:
        return None
    stand_in = Step(
        kind="toss",
        t_open_ms=opened_ms,
        t_settle_ms=at_ms,
        mass_g=0.0,
        mass_err_g=0.0,
        baseline_before_g=0.0,
        baseline_after_g=0.0,
    )
    params = CropParams()
    picked = pick_frames(frames, stand_in, params)
    if picked.before is None or picked.after is None:
        return None
    try:
        return crop_item(picked.before.jpeg, picked.after.jpeg, params).jpeg
    except (ValueError, RuntimeError):
        log.warning("the early crop did not come out, this toss waits for its settle")
        return None


def frame_bytes(frames: FramePick) -> list[bytes]:
    """The frames the QR reader gets: the after frame, then the peak frame.

    PLAN.md section 9 reads the tag from the after or the peak frame, and only those two.
    The before frame is the bin as it was a moment earlier, so anything readable in it
    belongs to something that was already there, not to this toss.
    """
    picked = [frames.after, frames.peak]
    return [frame.jpeg for frame in picked if frame is not None and frame.jpeg]


def _estimate_from(value: ValueEstimate, which: str) -> Estimate:
    """One of the four ranges, with the middle rounded to a figure a person would say.

    PLAN.md 21a item 47. Low and high keep every cent: the drawer draws the range, and
    rounding it would claim a precision nobody has. The middle is the number on the bin.
    """
    money_range = getattr(value, which)
    return Estimate(
        low=money_range.low,
        mid=round_money(money_range.mid),
        high=money_range.high,
        source=EstimateSource.model_estimate,
    )


# The vision answer, kept where the second half of the pipeline can read it ---


class VisionRecorder:
    """A vision provider that also remembers what it said, keyed by event.

    The `on_final` seam carries a label, a class and a method, and nothing else. The
    condition the model saw and the material it guessed would be lost between the two
    halves of the pipeline, and the repair rule needs the condition. So the glue wraps the
    provider rather than widening the seam, and no file in the identification lane changes.
    """

    def __init__(self, inner: VisionProvider, keep: int = VISION_KEEP) -> None:
        self.inner = inner
        self.keep = keep
        self.name = inner.name
        self.last_call: CallUsage | None = inner.last_call
        self.seen: dict[int, VisionResult] = {}

    def identify(self, crop: bytes, context: IdentifyContext) -> VisionResult:
        result = self.inner.identify(crop, context)
        self.last_call = self.inner.last_call
        self.seen[context.event_id] = result
        while len(self.seen) > self.keep:
            self.seen.pop(next(iter(self.seen)))
        return result

    def remember(self, event_id: int, result: VisionResult) -> None:
        """File an answer that was produced before the event had an id."""
        self.seen[event_id] = result
        while len(self.seen) > self.keep:
            self.seen.pop(next(iter(self.seen)))

    def of(self, event_id: int) -> VisionResult | None:
        """What the model said about this event, if a model was asked at all."""
        return self.seen.get(event_id)


# The pipeline ---------------------------------------------------------------


class PipelineDeps:
    """Everything one process needs to take a toss from the scale to the books."""

    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        bus: Bus,
        providers: Providers,
        embedder: Embedder,
        memory: MemoryIndex,
        vision: VisionRecorder,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.bus = bus
        self.providers = providers
        self.embedder = embedder
        self.memory = memory
        self.vision = vision
        self._ingest: IngestState | None = None
        self.identify = IdentifyDeps(
            session_factory=session_factory,
            providers=providers,
            embedder=embedder,
            memory=memory,
            settings=settings,
            bus=bus,
            on_final=self.finalise_event,
        )

    # Attachment ------------------------------------------------------------

    def attach(self, ingest: IngestState) -> None:
        """Hang this pipeline off the two seams the lanes left, and off the ask answer.

        `set_on_final` is a process global inside the identification lane. It is how a
        person's answer on `/api/corrections` reaches the engine without that route
        knowing anything about the engine.
        """
        ingest.on_event = self.on_event
        ingest.on_step_open = self.on_step_open
        ingest.current_round_id = self.current_round_id
        self._ingest = ingest
        set_on_final(self.finalise_event)

    def current_round_id(self) -> int | None:
        """Which round an event belongs to at the moment it is created.

        Only a round that is already open counts. Opening one is identification's job, so a
        scale running with nothing attached to it never starts a round on its own.
        """
        session = self.session_factory()
        try:
            current = rounds.open_round(session)
            return int(current.id) if current is not None else None
        finally:
            session.close()

    # Stage zero: the model starts while the scale is still settling ---------

    def on_step_open(self, opened_ms: float, baseline_g: float) -> None:
        """Start the vision call the moment the weight moves, not when it stops moving.

        PLAN.md section 7 waits `settle_ms` before it will call a step a step, and the
        model takes seconds more after that. The two do not have to be in a row: the item
        is in the picture as soon as it lands. This starts the call and `app.identify.early`
        holds it until identification asks. Nothing is written anywhere until the event row
        exists, so an aborted step leaves no trace but a log line.
        """
        ingest = self._ingest
        if ingest is None or not self.settings.identify_at_step_open:
            return
        if ingest.latest_g < baseline_g:
            # The scale is going down, so this is a bag going out or something coming back
            # and nothing will be identified. In the first real run this alone cost two
            # live calls, because a request already on the wire cannot be unsent when the
            # step settles the wrong way.
            log.debug("the step at %.0f ms is a removal, so nothing is asked", opened_ms)
            return
        if not len(ingest.frames):
            # No camera has sent anything, so there is no early picture to take and the
            # toss is a weight and nothing else. PLAN.md rule 6: that is a real event.
            log.debug("no frames in the ring, the step at %.0f ms waits for its settle",
                      opened_ms)
            return
        early.start(opened_ms, self._early_vision(ingest, opened_ms, baseline_g))

    async def _early_vision(
        self, ingest: IngestState, opened_ms: float, baseline_g: float
    ) -> early.EarlyResult:
        """Wait for the item to be in shot, cut it out, and ask the model about it."""
        delay_ms = float(self.settings.identify_open_delay_ms)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        frames = ingest.frames.snapshot()
        mass_g = max(0.0, ingest.latest_g - baseline_g)
        crop = await asyncio.to_thread(_early_crop, frames, opened_ms, opened_ms + delay_ms)
        if crop is None:
            log.info(
                "no usable frame %.0f ms after the step opened, this toss waits for its settle",
                delay_ms,
            )
            return None, None
        session = self.session_factory()
        try:
            # A tagged asset is identified off the tag, for nothing, in about 75 ms. Asking
            # the model about it as well is money spent on an answer that loses. The tag is
            # read again on the settled frames, which is where it decides; this only asks
            # whether there is any point making the call.
            if qr.match_asset(qr.read_tags(_early_frames(frames, opened_ms)), session):
                log.info("a tag is already in shot, so no early call was made")
                return None, None
            context = build_context(
                session,
                event_id=0,
                mass_g=mass_g,
                mass_err_g=0.0,
                settings=self.settings,
                # The scale has not settled, so the mass in the data block is what the
                # scale read a moment after the item landed. Say so rather than let the
                # model read a settled figure into it.
                hints={"mass": "measured before the scale settled"},
            )
        finally:
            session.close()
        started = time.perf_counter()
        answer = await asyncio.to_thread(self.providers.vision.identify, crop, context)
        log.info(
            "the early vision call answered in %d ms about %.0f g",
            int((time.perf_counter() - started) * 1000),
            mass_g,
        )
        return answer, crop

    # Stage one: a step becomes an identification ---------------------------

    async def on_event(
        self,
        event_id: int,
        crop: bytes | None,
        frames: FramePick,
        mass_g: float,
        mass_err_g: float,
    ) -> None:
        """What ingest calls. One await, so the seam stays as thin as Lane A left it."""
        await identify_event(
            event_id,
            crop,
            frame_bytes(frames),
            mass_g,
            mass_err_g,
            deps=self.identify,
        )

    # Stage two: an identification becomes money on the books ---------------

    async def finalise_event(
        self,
        event_id: int,
        label: str,
        item_class: models.ItemClass,
        method: models.IdentifyMethod,
    ) -> None:
        """Price one identified toss and post it. Never raises."""
        stage = "start"
        session = self.session_factory()
        try:
            stage = "load"
            event = session.get(models.Event, event_id)
            if event is None:
                log.error("event %d has no row left to post", event_id)
                return
            mass_g = float(event.mass_g or 0.0)
            when = _event_date(event)
            log.info(
                "event %d final: label=%s class=%s method=%s mass=%.1fg",
                event_id,
                label,
                item_class.value,
                method.value,
                mass_g,
            )

            stage = "lookup"
            asset_row = _asset_for(session, label, item_class, method)
            asset = to_asset_info(asset_row) if asset_row is not None else None
            catalog = None if asset is not None else _catalog_for(session, label)
            cls = _settled_class(item_class, asset, catalog)
            display = asset.description.lower()[:40] if asset is not None else label
            log.info(
                "event %d priced as %s: catalog=%s asset=%s",
                event_id,
                cls.value,
                catalog.label if catalog is not None else None,
                asset.tag if asset is not None else None,
            )

            stage = "estimate"
            seen = self.vision.of(event_id)
            # What a person answered when the bin asked. PLAN.md 21a item 38: the answer
            # is the difference between a sixteen gigabyte stick and a two hundred and
            # fifty six gigabyte one, so it is read before anything is priced.
            answers = read_answers(session, event_id)
            detail = answers.get(DETAIL_KEY, "")
            condition = _condition_of(seen, answers.get(DETAIL_CONDITION_KEY))
            # PLAN.md 21a item 25. The value estimate is a second model call, and Lane K
            # measured it slower than the vision call every single time, which is what put
            # an unpriced ticket at six seconds. It comes off the critical path: the label
            # and the mass reach all three surfaces now, and the figure follows.
            cached = (
                estimate_cache.read_estimate(
                    estimate_cache.estimate_key(
                        display, seen or _vision_stand_in(display, cls), detail
                    )
                )
                if cls is ItemClass.untracked
                else None
            )
            valuing = cls is ItemClass.untracked and cached is None

            parts = _Pricing(
                event_id=event_id,
                label=display,
                cls=cls,
                mass_g=mass_g,
                when=when,
                catalog=catalog,
                asset=asset,
                asset_row=asset_row,
                condition=condition,
                description=seen.description if seen is not None else "",
                detail=detail,
            )
            stage = await self._post_pass(session, event, parts, cached, valuing=valuing)
            if not valuing:
                log.info("event %d is posted", event_id)
                return

            stage = "estimate"
            # The same picture the vision call looked at. The estimator used to see the
            # word alone, which is how a hundred and fifty dollar mouse came back at
            # twelve dollars. PLAN.md 21a item 29.
            estimate = await self._estimate(
                cls, display, mass_g, seen, read_jpeg(event_id, "crop", self.settings), detail
            )
            if estimate is None:
                log.info("event %d has no estimate, the ticket stands as it is", event_id)
                return
            written = session.get(models.ItemRecord, event_id)
            if written is None or written.label != display[:40]:
                # A person answered again while the estimate was out. The figure belongs to
                # the label that was asked about, not to whatever the ticket says now.
                log.info(
                    "event %d was relabelled while it was valued, so the estimate is dropped",
                    event_id,
                )
                return
            stage = await self._post_pass(session, event, parts, estimate, valuing=False)
            log.info("event %d is posted with its value", event_id)
        except Exception:
            session.rollback()
            log.exception(
                "event %d could not be posted, it failed at the %s stage and keeps its "
                "last good status",
                event_id,
                stage,
            )
        finally:
            session.close()

    async def _post_pass(
        self,
        session: Session,
        event: models.Event,
        parts: _Pricing,
        estimate: ValueEstimate | None,
        *,
        valuing: bool,
    ) -> str:
        """Price the ticket, write it, post it and say so. Returns the stage it reached.

        Runs once for a ticket the catalog prices, and twice for one it does not: first
        with no figure, so the bin and the phone answer at once, then again with it.
        Re-posting reverses the first pass's entries, which is `_post_entries` doing what
        PLAN.md section 11 asks, and an untracked item posts nothing to reverse.
        """
        event_id = parts.event_id
        record = _build_record(
            event_id=event_id,
            label=parts.label,
            cls=parts.cls,
            mass_g=parts.mass_g,
            when=parts.when,
            catalog=parts.catalog,
            asset=parts.asset,
            condition=parts.condition,
            estimate=estimate,
            description=parts.description,
            detail=parts.detail,
        )

        engine_settings = EngineSettings.from_settings(self.settings)
        scores = engine_options.score_options(record, engine_settings, parts.asset)
        ranking = engine_options.summarise(scores, engine_settings)
        log.info(
            "event %d scored: best=%s greenest=%s saved=%d tone=%s%s",
            event_id,
            ranking.best_option.value if ranking.best_option is not None else None,
            ranking.greenest_option.value if ranking.greenest_option is not None else None,
            ranking.saved_if_followed_cents,
            ranking.tone,
            " (still being valued)" if valuing else "",
        )

        words = self._words(record, ranking, scores, valuing=valuing)
        checked: sense_check.SenseCheck | None = None
        if not valuing:
            # PLAN.md 21a item 50. The last reader before the bin speaks. It runs before
            # anything is written, so a veto never has to be unposted.
            checked = await self._sense_gate(event_id, record, ranking, scores, words)
            if checked is not None and checked.vetoed:
                self._veto_to_ask(session, event, event_id, checked)
                return "ask"
            if checked is not None and checked.verdict == "rewrite":
                words = words.rewritten(checked)

        _write_item_record(session, record)
        _write_option_scores(session, event_id, scores)

        posted = _post_entries(session, record, parts.asset, engine_settings)
        log.info("event %d posted %d journal entries", event_id, posted)

        if parts.asset_row is not None:
            parts.asset_row.status = models.AssetStatus.disposed
            parts.asset_row.disposed_event_id = event_id
            log.info("asset %s is off the register on event %d", parts.asset_row.tag, event_id)

        event.status = models.EventStatus.posted
        if checked is not None:
            _store_sense(session, event_id, checked)
        session.commit()

        self._publish(session, event, record, ranking, words)
        metrics.publish_metrics(session, self.bus)
        return "publish"

    # The pieces ------------------------------------------------------------

    async def _estimate(
        self,
        cls: ItemClass,
        label: str,
        mass_g: float,
        seen: VisionResult | None,
        crop: bytes | None = None,
        detail: str = "",
    ) -> ValueEstimate | None:
        """What an untracked object is worth, from the cache when it was priced before.

        PLAN.md section 9: only unknown objects are estimated, and the same label is never
        estimated twice. A call that fails leaves the record without estimates, which shows
        on the ticket as fewer options, never as a made-up number.
        """
        if cls is not ItemClass.untracked:
            return None
        vision = seen or _vision_stand_in(label, cls)
        key = estimate_cache.estimate_key(label, vision, detail)
        cached = estimate_cache.read_estimate(key)
        if cached is not None:
            return cached
        try:
            estimate = await asyncio.wait_for(
                asyncio.to_thread(
                    self.providers.estimator.estimate, label, vision, mass_g, crop, detail
                ),
                timeout=self.settings.llm_timeout_s,
            )
        except TimeoutError:
            log.warning("the estimate for %s timed out", label)
            return None
        except Exception:
            log.exception("the estimate for %s failed", label)
            return None
        estimate_cache.write_estimate(key, estimate)
        return estimate

    def _words(
        self,
        record: ItemRecord,
        ranking: engine_options.Ranking,
        scores: list[OptionScore],
        *,
        valuing: bool,
    ) -> _Words:
        """Every string the three surfaces draw for one ticket, built once.

        The sense gate reads these and may replace two of them, so they are built before
        anything is written and carried through rather than rebuilt at the end.
        """
        table = engine_options.by_option(scores)
        trash = table.get(Option.trash)
        blocked = trash is not None and not trash.allowed
        title = title_for(record.label)
        line = advice_line(record, ranking, blocked, self.settings.speak_up_cents)
        tone = TONES.get(ranking.tone, "neutral")
        if line == FINE_TO_BIN and not blocked:
            # The words and the colour have to agree. Amber beside "Fine to bin" reads as
            # the bin hedging about something it has just called fine.
            tone = "green"
        cents = headline_cents(record)
        big_money = signed_money(cents)[:16]
        lcd_money = lcd_big(cents)
        if valuing:
            # No figure yet, so none is drawn. DESIGN.md section 8: say what is happening.
            big_money = VALUING_BIG
            lcd_money = VALUING_BIG
            line = VALUING_LINE
            tone = "neutral"
        return _Words(
            title=title,
            line=line,
            tone=tone,
            big=big_money,
            lcd_money=lcd_money,
            blocked=blocked,
            best_option=ranking.best_option,
        )

    async def _sense_gate(
        self,
        event_id: int,
        record: ItemRecord,
        ranking: engine_options.Ranking,
        scores: list[OptionScore],
        words: _Words,
    ) -> sense_check.SenseCheck | None:
        """One reader on the finished ticket, off the event loop and under its own limit."""
        if not sense_check.should_check(record, ranking):
            return None
        seen = self.vision.of(event_id)
        description = seen.description if seen is not None else ""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    sense_check.check,
                    record,
                    ranking,
                    scores,
                    description,
                    words.title,
                    words.line,
                    self.settings,
                ),
                timeout=self.settings.sense_check_timeout_s + 0.5,
            )
        except TimeoutError:
            log.warning("the sense gate on event %d timed out, the words stand", event_id)
        except Exception:
            log.exception("the sense gate on event %d failed, the words stand", event_id)
        return None

    def _veto_to_ask(
        self,
        session: Session,
        event: models.Event,
        event_id: int,
        checked: sense_check.SenseCheck,
    ) -> None:
        """A vetoed ticket is a question, not a claim. Nothing confident is drawn.

        Anything an earlier pass posted is reversed first, because PLAN.md section 11 never
        deletes an entry and a person is about to say what this really was.
        """
        log.info("event %d was vetoed by the sense gate: %s", event_id, checked.reason)
        posted = session.scalars(
            select(models.JournalEntry.id).where(models.JournalEntry.event_id == event_id)
        ).first()
        if posted is not None:
            ledger_queries.void_event(session, event_id)
        seen = self.vision.of(event_id)
        description = seen.description if seen is not None else ""
        _store_sense(session, event_id, checked)
        open_ask(session, event, {}, self.identify, description)
        session.commit()
        self.bus.publish(UiEventUpdated(event=event_summary(session, event)), CHANNEL_UI)
        metrics.publish_metrics(session, self.bus)

    def _publish(
        self,
        session: Session,
        event: models.Event,
        record: ItemRecord,
        ranking: engine_options.Ranking,
        words: _Words,
    ) -> None:
        """Tell the dashboard, the phone and the bin, in that order."""
        event_id = int(event.id)
        self.bus.publish(UiEventUpdated(event=event_summary(session, event)), CHANNEL_UI)
        for entry in ledger_queries.list_entries(session, event_id=event_id):
            self.bus.publish(UiJournalPosted(entry=entry), CHANNEL_UI)

        if words.best_option is not None:
            self.bus.publish(
                PhoneResult(
                    event_id=event_id,
                    title=words.title[:60],
                    big=words.big,
                    line=words.line,
                    tone=words.tone,
                    best_option=models.OptionKind(words.best_option.value),
                ),
                CHANNEL_PHONE,
            )
        else:
            log.warning("event %d has no allowed option, so the phone gets no result", event_id)
        self.bus.publish(
            lcd.result(words.title, words.lcd_money, words.line, words.tone), CHANNEL_BIN
        )


# Lookups --------------------------------------------------------------------


def _asset_for(
    session: Session,
    label: str,
    item_class: models.ItemClass,
    method: models.IdentifyMethod,
) -> models.Asset | None:
    """The register row, looked up by tag. A QR read is a tag, and so is a person typing one."""
    if (
        method is not models.IdentifyMethod.qr
        and item_class is not models.ItemClass.fixed_asset
    ):
        return None
    return session.scalars(select(models.Asset).where(models.Asset.tag == label)).first()


def _catalog_for(session: Session, label: str) -> CatalogItem | None:
    """The catalog row for this label, the database first, then the seed file."""
    row = session.scalars(
        select(models.CatalogItem).where(models.CatalogItem.label == label)
    ).first()
    if row is not None:
        return to_catalog_item(row)
    try:
        return engine_records.catalog_by_label().get(label)
    except (OSError, KeyError, ValueError):
        log.warning("the catalog seed file is unreadable")
        return None


# Building and posting -------------------------------------------------------


def _build_record(
    *,
    event_id: int,
    label: str,
    cls: ItemClass,
    mass_g: float,
    when: date,
    catalog: CatalogItem | None,
    asset: AssetInfo | None,
    condition: Condition,
    estimate: ValueEstimate | None,
    description: str = "",
    detail: str = "",
) -> ItemRecord:
    """Assemble what the engine scores. The catalog wins on materials, the model fills gaps."""
    mix: dict[str, float] = {}
    if catalog is not None and catalog.material_mix:
        mix = dict(catalog.material_mix)
    elif estimate is not None and estimate.material_mix:
        mix = {str(key): value for key, value in estimate.material_mix.items()}

    flags = sorted(
        {
            *(catalog.regulatory_flags if catalog is not None else ()),
            *(str(flag) for flag in (estimate.regulatory_flags if estimate is not None else ())),
        }
    )

    return engine_records.build_item_record(
        event_id=event_id,
        label=label,
        item_class=cls,
        mass_g=mass_g,
        event_date=when,
        catalog=catalog,
        asset=asset,
        condition=condition,
        fmv=_estimate_from(estimate, "fmv") if estimate is not None else None,
        repair=_estimate_from(estimate, "repair") if estimate is not None else None,
        replacement_cents=(
            round_money(estimate.replacement.mid) if estimate is not None else None
        ),
        replacement_source=EstimateSource.model_estimate if estimate is not None else None,
        scrap_cents=round_money(estimate.scrap.mid) if estimate is not None else None,
        scrap_source=EstimateSource.model_estimate if estimate is not None else None,
        material_mix=mix or None,
        regulatory_flags=flags or None,
        description=description,
        detail=detail,
    )


def _post_entries(
    session: Session,
    record: ItemRecord,
    asset: AssetInfo | None,
    engine_settings: EngineSettings,
) -> int:
    """Post what this class of item owes the books. Returns how many entries were written.

    An event that was already posted and is then answered again is reversed first, because
    PLAN.md section 11 never deletes an entry. The reversal and the fresh entry both stay
    on the ticket, which is what an audit trail is for.
    """
    event_id = record.event_id
    already = session.scalars(
        select(models.JournalEntry.id).where(models.JournalEntry.event_id == event_id)
    ).first()
    if already is not None:
        reversed_ids = ledger_queries.void_event(session, event_id)
        log.info("event %d was re-posted, %d entries reversed", event_id, len(reversed_ids))

    posted = 0
    if record.item_class is ItemClass.fixed_asset and asset is not None:
        ledger_queries.post_entry(
            session, ledger_journal.fixed_asset_disposal(record, asset), event_id=event_id
        )
        posted += 1
        effect = tax_effect_for(Option.trash, record, engine_settings, asset)
        if effect is not None:
            ledger_queries.post_entry(
                session,
                ledger_journal.tax_memo(record, asset, effect),
                event_id=event_id,
            )
            posted += 1
    elif record.item_class is ItemClass.inventory:
        entry = ledger_journal.inventory_toss(record)
        if entry is not None:
            ledger_queries.post_entry(session, entry, event_id=event_id)
            posted += 1
        else:
            log.info("event %d has no cost basis, so nothing was written off", event_id)
    else:
        flag = ledger_journal.untracked_flag(record, engine_settings)
        if flag is not None:
            log.warning("event %d raised %s: %s", event_id, flag.kind, flag.message)
    session.flush()
    return posted


# Row writers ----------------------------------------------------------------


def _write_item_record(session: Session, record: ItemRecord) -> None:
    """Upsert `item_record`. One row per event, rewritten when a person corrects the label."""
    row = session.get(models.ItemRecord, record.event_id)
    if row is None:
        row = models.ItemRecord(event_id=record.event_id)
        session.add(row)
    row.label = record.label[:40]
    row.item_class = models.ItemClass(record.item_class.value)
    row.mass_g = record.mass_g
    row.condition = record.condition.value
    row.material_mix_json = json.dumps(record.material_mix)
    row.regulatory_flags_json = json.dumps(record.regulatory_flags)
    row.book_value_cents = record.book_value_cents
    row.tax_basis_cents = record.tax_basis_cents
    row.asset_id = record.asset_id
    row.cost_basis_cents = record.cost_basis_cents or 0
    row.fmv_low = record.fmv_low
    row.fmv_mid = record.fmv_mid
    row.fmv_high = record.fmv_high
    row.fmv_source = record.fmv_source.value if record.fmv_source is not None else None
    row.repair_low = record.repair_low
    row.repair_mid = record.repair_mid
    row.repair_high = record.repair_high
    row.repair_source = record.repair_source.value if record.repair_source is not None else None
    row.replacement_cents = record.replacement_cents
    row.replacement_source = (
        record.replacement_source.value if record.replacement_source is not None else None
    )
    row.scrap_cents = record.scrap_cents
    row.scrap_source = record.scrap_source.value if record.scrap_source is not None else None
    session.flush()


def _write_option_scores(session: Session, event_id: int, scores: list[OptionScore]) -> None:
    """Replace this event's option rows. The table holds one row per event and option."""
    session.execute(delete(models.OptionScore).where(models.OptionScore.event_id == event_id))
    for score in scores:
        session.add(
            models.OptionScore(
                event_id=event_id,
                option=models.OptionKind(score.option.value),
                allowed=score.allowed,
                blocked_reason=score.blocked_reason,
                cash_cents=score.cash_cents,
                tax_effect_cents=score.tax_effect_cents,
                net_after_tax_cents=score.net_after_tax_cents,
                kg_co2e=score.kg_co2e,
                kg_landfill=score.kg_landfill,
                needs_human_review=score.needs_human_review,
                notes_json=json.dumps(score.notes),
                rule_ids_json=json.dumps(score.rule_ids),
                rank=score.rank,
            )
        )
    session.flush()


# Helpers --------------------------------------------------------------------


def _settled_class(
    item_class: models.ItemClass,
    asset: AssetInfo | None,
    catalog: CatalogItem | None,
) -> ItemClass:
    """What the item really is. The register beats the catalog, the catalog beats the model."""
    if asset is not None:
        return ItemClass.fixed_asset
    if catalog is not None:
        return catalog.item_class
    return ItemClass(item_class.value)


def _condition_of(seen: VisionResult | None, answered: str | None = None) -> Condition:
    """What condition this thing is in. A person who was asked beats the camera."""
    for candidate in (answered, seen.condition if seen is not None else None):
        if not candidate:
            continue
        try:
            return Condition(candidate)
        except ValueError:
            continue
    return Condition.unknown


def _vision_stand_in(label: str, cls: ItemClass) -> VisionResult:
    """A code-built vision result for the estimator when no model looked at this toss.

    A QR tag and a remembered exemplar both end the run before any vision call. The
    estimator still wants the shape, so it gets one built here out of what the pipeline
    already decided. Nothing a person typed reaches it.
    """
    return VisionResult.model_validate(
        {
            "label": label,
            "class": models.ItemClass(cls.value),
            "confidence": 1.0,
            "candidates": [],
            "condition": "unknown",
            "visible_text": "",
            "provider": "local",
            "model": "pipeline",
        }
    )


def build_pipeline(
    settings: Settings,
    session_factory: Callable[[], Session],
    bus: Bus,
) -> PipelineDeps:
    """Build one pipeline: the providers, the embedder, the memory index, and the two hooks."""
    base = build_providers(settings)
    recorder = VisionRecorder(base.vision)
    providers = Providers(vision=recorder, estimator=base.estimator, name=base.name)
    log.info("pipeline built on the %s provider", base.name)
    return PipelineDeps(
        settings=settings,
        session_factory=session_factory,
        bus=bus,
        providers=providers,
        embedder=get_embedder(),
        memory=get_memory(),
        vision=recorder,
    )


def build_default_pipeline(settings: Settings) -> PipelineDeps:
    """The process-wide pipeline, on the process-wide session factory and bus."""
    from app.db import get_session_factory

    return build_pipeline(settings, get_session_factory(), get_bus())


__all__ = [
    "PipelineDeps",
    "VisionRecorder",
    "advice_line",
    "build_default_pipeline",
    "build_pipeline",
    "frame_bytes",
    "headline_cents",
    "lcd_big",
    "signed_money",
    "title_for",
    "to_catalog_item",
]
