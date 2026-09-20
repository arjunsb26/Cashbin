"""Every wire message and every REST body. This file is the cross-lane contract.

PLAN.md section 6 defines the sockets, section 9 the model output, section 14 the REST surface.
Changing anything here means changing PLAN.md first, per section 21.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import (
    AssetStatus,
    CropQuality,
    EventKind,
    EventStatus,
    IdentifyMethod,
    ItemClass,
    JournalBasis,
    OptionKind,
    ReviewKind,
    ReviewStatus,
    TaxMethod,
)

# Field limits from PLAN.md section 6. The firmware draws nothing wider than these.
LCD_LINE_MAX = 20
LCD_BIG_MAX = 7
VISIBLE_TEXT_MAX = 120
DESCRIPTION_MAX = 80
LABEL_MAX = 40


class WireModel(BaseModel):
    """Unknown fields are ignored on every wire message, per PLAN.md section 6."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ApiModel(BaseModel):
    """REST bodies. Extra input is dropped rather than rejected, so old clients keep working."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, from_attributes=True)


# Validated free text -------------------------------------------------------

_LABEL_ALLOWED = re.compile(r"^[a-z0-9 -]+$")
_KEY_ALLOWED = re.compile(r"^[a-z0-9_]+$")
_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def normalise_label(raw: Any) -> str:
    """Turn outside text into a label, or refuse it.

    CLAUDE.md "Free text and images into models" item 1. Trim, fold to plain characters,
    lowercase, then allow only letters, digits, spaces and hyphens, at most 40 characters.
    Anything else is refused rather than patched, because a label is used as a key.
    """
    if not isinstance(raw, str):
        raise ValueError("label must be text")
    text = unicodedata.normalize("NFKC", raw)
    text = _CONTROL.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip().lower()
    if not text:
        raise ValueError("label is empty")
    if len(text) > LABEL_MAX:
        raise ValueError(f"label is longer than {LABEL_MAX} characters")
    if not _LABEL_ALLOWED.match(text):
        raise ValueError("label may use only letters, digits, spaces and hyphens")
    return text


def normalise_key(raw: Any) -> str:
    """Same wall for machine keys such as material names and regulatory flags."""
    if not isinstance(raw, str):
        raise ValueError("key must be text")
    text = unicodedata.normalize("NFKC", raw)
    text = _CONTROL.sub(" ", text)
    text = _WHITESPACE.sub("_", text).strip("_").lower()
    if not text:
        raise ValueError("key is empty")
    if len(text) > LABEL_MAX:
        raise ValueError(f"key is longer than {LABEL_MAX} characters")
    if not _KEY_ALLOWED.match(text):
        raise ValueError("key may use only letters, digits and underscores")
    return text


class ValidatedLabel(str):
    """A label that has been through normalise_label. Use it wherever outside text lands."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls._validate,
            serialization=core_schema.to_string_ser_schema(),
            metadata={
                "pydantic_js_input_core_schema": core_schema.str_schema(
                    max_length=LABEL_MAX, pattern=_LABEL_ALLOWED.pattern
                )
            },
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, _source: Any, _handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "maxLength": LABEL_MAX,
            "pattern": _LABEL_ALLOWED.pattern,
            "description": "Lowercase label. Letters, digits, spaces and hyphens only.",
        }

    @classmethod
    def _validate(cls, value: Any) -> ValidatedLabel:
        return cls(normalise_label(value))


class MaterialKey(str):
    """A material or flag key such as food_waste or electronics."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(
            cls._validate, serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, _source: Any, _handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "maxLength": LABEL_MAX,
            "pattern": _KEY_ALLOWED.pattern,
            "description": "Lowercase key. Letters, digits and underscores only.",
        }

    @classmethod
    def _validate(cls, value: Any) -> MaterialKey:
        return cls(normalise_key(value))


def _clean_free_text(value: Any, limit: int) -> Any:
    """Outside prose, made safe to store and to draw. Never an instruction, always data."""
    if not isinstance(value, str):
        return value
    cleaned = _CONTROL.sub(" ", unicodedata.normalize("NFKC", value))
    return _WHITESPACE.sub(" ", cleaned).strip()[:limit]


def lcd_text(raw: Any, limit: int) -> Any:
    """Fold to plain ASCII, flatten whitespace, then cut to the limit.

    PLAN.md section 6 states two things about LCD fields: a hard width, and that the backend
    is responsible for truncation. Doing it in the type makes both true at once, so an
    over-long string cannot reach the bin no matter who built the message. The example in
    firmware_contract.md carries a 21 character second line, which lands here as 20.
    """
    if not isinstance(raw, str):
        return raw
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return _WHITESPACE.sub(" ", folded).strip()[:limit].rstrip()


def _cut_line(raw: Any) -> Any:
    return lcd_text(raw, LCD_LINE_MAX)


def _cut_big(raw: Any) -> Any:
    """The big figure carries no spaces, so a wide number keeps its sign and leading digits."""
    value = lcd_text(raw, LCD_LINE_MAX)
    return value.replace(" ", "")[:LCD_BIG_MAX] if isinstance(value, str) else value


LcdLine: TypeAlias = Annotated[
    str, BeforeValidator(_cut_line), StringConstraints(max_length=LCD_LINE_MAX)
]
LcdBig: TypeAlias = Annotated[
    str, BeforeValidator(_cut_big), StringConstraints(max_length=LCD_BIG_MAX)
]
LcdColour: TypeAlias = Literal["green", "amber", "red", "neutral"]
Probability: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]

# How hard the host is asked to think, and which queue it is asked to use. Both lists are
# the installed SDK's own, so a value that would be a 400 cannot be set.
ReasoningEffort: TypeAlias = Literal["none", "minimal", "low", "medium", "high"]
ServiceTier: TypeAlias = Literal["auto", "default", "flex", "scale", "priority", "fast"]

FLAG_ELECTRONICS = "electronics"
FLAG_BATTERY = "battery"


# Bin to backend (/ws/bin) --------------------------------------------------


class BinHello(WireModel):
    type: Literal["hello"] = "hello"
    fw: str = Field(max_length=16)
    device: str = Field(max_length=32)


class BinWeight(WireModel):
    type: Literal["weight"] = "weight"
    t: int = Field(description="Device milliseconds. Kept for debugging only.")
    g: float = Field(description="Raw grams after calibration. The backend does the filtering.")


class BinPong(WireModel):
    type: Literal["pong"] = "pong"
    t: int


class BinButton(WireModel):
    type: Literal["button"] = "button"
    id: str = Field(max_length=8)


BinToBackend: TypeAlias = Annotated[
    BinHello | BinWeight | BinPong | BinButton, Field(discriminator="type")
]


# Backend to bin ------------------------------------------------------------


class BinPing(WireModel):
    type: Literal["ping"] = "ping"


class BinTare(WireModel):
    type: Literal["tare"] = "tare"


class ScreenIdle(WireModel):
    type: Literal["screen"] = "screen"
    s: Literal["idle"] = "idle"


class ScreenThinking(WireModel):
    type: Literal["screen"] = "screen"
    s: Literal["thinking"] = "thinking"


class ScreenResult(WireModel):
    type: Literal["screen"] = "screen"
    s: Literal["result"] = "result"
    l1: LcdLine
    big: LcdBig
    l2: LcdLine
    c: LcdColour


class ScreenAsk(WireModel):
    type: Literal["screen"] = "screen"
    s: Literal["ask"] = "ask"
    l1: LcdLine
    l2: LcdLine


class ScreenOffline(WireModel):
    type: Literal["screen"] = "screen"
    s: Literal["offline"] = "offline"


ScreenCommand: TypeAlias = Annotated[
    ScreenIdle | ScreenThinking | ScreenResult | ScreenAsk | ScreenOffline,
    Field(discriminator="s"),
]

BackendToBin: TypeAlias = Annotated[
    Annotated[BinPing, Field()] | Annotated[BinTare, Field()] | ScreenCommand,
    Field(discriminator="type"),
]


# Phone to backend (/ws/phone, text frames only; binary frames are JPEG bytes) ----


class PhoneHello(WireModel):
    type: Literal["hello"] = "hello"
    ua: str = Field(default="", max_length=200)


class PhonePong(WireModel):
    type: Literal["pong"] = "pong"


PhoneToBackend: TypeAlias = Annotated[PhoneHello | PhonePong, Field(discriminator="type")]


# Backend to phone ----------------------------------------------------------


class AskCandidate(WireModel):
    label: ValidatedLabel
    p: Probability


class PhoneResult(WireModel):
    type: Literal["result"] = "result"
    event_id: int
    title: str = Field(max_length=60)
    big: str = Field(max_length=16)
    line: str = Field(max_length=80)
    tone: LcdColour
    best_option: OptionKind


class PhoneAsk(WireModel):
    type: Literal["ask"] = "ask"
    event_id: int
    candidates: list[AskCandidate] = Field(default_factory=list, max_length=4)
    crop_url: str | None = None
    looks_like: str | None = Field(default=None, max_length=DESCRIPTION_MAX)


class PhoneIdle(WireModel):
    type: Literal["idle"] = "idle"


class PhonePing(WireModel):
    type: Literal["ping"] = "ping"


BackendToPhone: TypeAlias = Annotated[
    PhoneResult | PhoneAsk | PhoneIdle | PhonePing, Field(discriminator="type")
]


# Backend to dashboard (/ws/ui) ---------------------------------------------

UiTopic: TypeAlias = Literal[
    "weight",
    "event.created",
    "event.updated",
    "journal.posted",
    "ask.opened",
    "ask.resolved",
    "metrics.updated",
    "device.status",
]


class UiWeight(WireModel):
    """Downsampled to 10 Hz. `t` is backend arrival seconds, one clock for everything."""

    type: Literal["weight"] = "weight"
    t: float
    g: float
    device_t: int | None = None


class UiEventCreated(WireModel):
    type: Literal["event.created"] = "event.created"
    event: EventSummary


class UiEventUpdated(WireModel):
    type: Literal["event.updated"] = "event.updated"
    event: EventSummary


class UiJournalPosted(WireModel):
    type: Literal["journal.posted"] = "journal.posted"
    entry: JournalEntryRead


class UiAskOpened(WireModel):
    type: Literal["ask.opened"] = "ask.opened"
    event_id: int
    # Empty when the model had no guess worth drawing as a button. The question is then
    # the picture, what the model says it sees, and Something else.
    candidates: list[AskCandidate] = Field(default_factory=list, max_length=4)
    crop_url: str | None = None
    # The model's plain words about what it is looking at, when it had any. Shown beside
    # the buttons so a person knows what the camera saw before they answer.
    looks_like: str | None = Field(default=None, max_length=DESCRIPTION_MAX)


class UiAskResolved(WireModel):
    type: Literal["ask.resolved"] = "ask.resolved"
    event_id: int
    label: ValidatedLabel
    by: str = Field(default="person", max_length=40)


class UiMetricsUpdated(WireModel):
    type: Literal["metrics.updated"] = "metrics.updated"
    summary: SummaryResponse
    round: RoundRead | None = None


class UiDeviceStatus(WireModel):
    type: Literal["device.status"] = "device.status"
    device: Literal["bin", "phone"]
    connected: bool
    last_seen: str | None = None
    detail: str | None = Field(default=None, max_length=120)


UiMessage: TypeAlias = Annotated[
    UiWeight
    | UiEventCreated
    | UiEventUpdated
    | UiJournalPosted
    | UiAskOpened
    | UiAskResolved
    | UiMetricsUpdated
    | UiDeviceStatus,
    Field(discriminator="type"),
]


# Model output, validated before anything reads it (PLAN.md section 9) ------


class VisionCandidate(ApiModel):
    label: ValidatedLabel
    p: Probability


class VisionResult(ApiModel):
    """The only shape a vision call may produce. Nothing outside these fields is read."""

    label: ValidatedLabel
    item_class: ItemClass = Field(alias="class")
    confidence: Probability
    candidates: list[VisionCandidate] = Field(default_factory=list, max_length=5)
    material: MaterialKey | None = None
    condition: Literal["working", "broken", "unknown"] = "unknown"
    # What the camera is looking at, in plain words, whatever the label came out as. It is
    # what a person reads when the bin has to ask, and it is what the estimator prices when
    # the thing is not in the catalog.
    description: str = Field(default="", max_length=DESCRIPTION_MAX)
    visible_text: str = Field(default="", max_length=VISIBLE_TEXT_MAX)
    provider: str = Field(default="", max_length=40)
    model: str = Field(default="", max_length=80)

    @field_validator("visible_text", mode="before")
    @classmethod
    def _cap_visible_text(cls, value: Any) -> Any:
        """Text read off a sign is data. Strip control characters and cut it to the cap."""
        return _clean_free_text(value, VISIBLE_TEXT_MAX)

    @field_validator("description", mode="before")
    @classmethod
    def _cap_description(cls, value: Any) -> Any:
        """The model's own words about the object, treated exactly like a sign: as data."""
        return _clean_free_text(value, DESCRIPTION_MAX)


class MoneyRange(ApiModel):
    """An estimate in integer cents with its rationale. Low, mid and high must be ordered."""

    low: int
    mid: int
    high: int
    rationale: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _ordered(self) -> MoneyRange:
        if not self.low <= self.mid <= self.high:
            raise ValueError("money range must satisfy low <= mid <= high")
        return self


class ValueEstimate(ApiModel):
    """The only shape an estimator call may produce."""

    label: ValidatedLabel
    fmv: MoneyRange
    repair: MoneyRange
    replacement: MoneyRange
    scrap: MoneyRange
    material_mix: dict[MaterialKey, float] = Field(default_factory=dict)
    regulatory_flags: list[MaterialKey] = Field(default_factory=list, max_length=8)
    provider: str = Field(default="", max_length=40)
    model: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def _mix_sums_to_one(self) -> ValueEstimate:
        if self.material_mix:
            total = sum(self.material_mix.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError("material mix fractions must sum to 1")
            if any(v < 0.0 for v in self.material_mix.values()):
                raise ValueError("material mix fractions must not be negative")
        return self


# REST bodies (PLAN.md section 14) -----------------------------------------


class BrandInfo(ApiModel):
    """The product name lives in brand.json at the repo root and nowhere else."""

    name: str = Field(max_length=40)
    short_name: str = Field(max_length=20)
    tagline: str = Field(max_length=120)


class HealthResponse(ApiModel):
    status: Literal["ok", "degraded"]
    version: str
    db: bool
    product_name: str


class EstimateRef(ApiModel):
    """PLAN.md rule 5. An estimate carries its range and where it came from."""

    low: int | None = None
    mid: int | None = None
    high: int | None = None
    source: Literal["catalog", "register", "model_estimate", "human"] | None = None


class EventSummary(ApiModel):
    id: int
    created_at: str
    kind: EventKind
    status: EventStatus
    mass_g: float | None = None
    mass_err_g: float | None = None
    label: str | None = None
    item_class: ItemClass | None = Field(default=None, alias="class")
    crop_url: str | None = None
    crop_quality: CropQuality | None = None
    net_book_cents: int | None = None
    # What the journal actually posted for this ticket, on the books, as an income
    # statement amount: negative for a loss, positive for a gain, null when nothing
    # posted at all. `net_book_cents` is a book value and answers a different question.
    posted_cents: int | None = None
    is_estimate: bool = False
    best_option: OptionKind | None = None
    saved_if_followed_cents: int | None = None
    # Things the close would raise about this ticket, so a person sees them where they
    # can act on them. Today the only one is possible_unrecorded_asset.
    flags: list[str] = Field(default_factory=list)
    round_id: int | None = None


class EventListResponse(ApiModel):
    events: list[EventSummary] = Field(default_factory=list)


class IdentificationRead(ApiModel):
    id: int
    event_id: int
    method: IdentifyMethod
    label: str | None = None
    description: str | None = None
    item_class: ItemClass | None = Field(default=None, alias="class")
    confidence: float | None = None
    candidates: list[VisionCandidate] = Field(default_factory=list)
    posterior: dict[str, float] = Field(default_factory=dict)
    used_mass_prior: bool = False
    latency_ms: int | None = None
    cost_microusd: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    is_final: bool = False
    provider: str | None = None
    model: str | None = None


class ItemRecordRead(ApiModel):
    event_id: int
    label: str
    item_class: ItemClass = Field(alias="class")
    mass_g: float
    condition: Literal["working", "broken", "unknown"] = "unknown"
    material_mix: dict[str, float] = Field(default_factory=dict)
    regulatory_flags: list[str] = Field(default_factory=list)
    book_value_cents: int = 0
    tax_basis_cents: int = 0
    asset_id: int | None = None
    cost_basis_cents: int = 0
    fmv: EstimateRef = Field(default_factory=EstimateRef)
    repair: EstimateRef = Field(default_factory=EstimateRef)
    replacement_cents: int | None = None
    replacement_source: str | None = None
    scrap_cents: int | None = None
    scrap_source: str | None = None


class OptionScoreRead(ApiModel):
    id: int
    event_id: int
    option: OptionKind
    allowed: bool
    blocked_reason: str | None = None
    cash_cents: int
    tax_effect_cents: int
    net_after_tax_cents: int
    kg_co2e: float | None = None
    # What choosing this option instead of the bin avoids, as a positive number. WARM's
    # source reduction factors are negative because they are avoided emissions, so
    # `kg_co2e` on a resale reads as a negative figure that nobody can act on. This is
    # the same fact the other way up. `kg_co2e` is left exactly as it is for the audit.
    kg_co2e_avoided: float | None = None
    kg_landfill: float = 0.0
    needs_human_review: bool = False
    notes: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    rank: int | None = None


class JournalLineRead(ApiModel):
    id: int
    entry_id: int
    account: str
    account_name: str | None = None
    debit_cents: int = 0
    credit_cents: int = 0


class JournalEntryRead(ApiModel):
    id: int
    event_id: int | None = None
    close_id: int | None = None
    posted_at: str
    memo: str = ""
    basis: JournalBasis
    evidence: dict[str, Any] = Field(default_factory=dict)
    lines: list[JournalLineRead] = Field(default_factory=list)


class CorrectionRead(ApiModel):
    id: int
    event_id: int
    field: str
    old_value: str | None = None
    new_value: str | None = None
    by: str
    created_at: str


class EventDetail(ApiModel):
    event: EventSummary
    trace: list[list[float]] = Field(
        default_factory=list, description="Pairs of [t_seconds, grams] around the step."
    )
    frame_before_url: str | None = None
    frame_after_url: str | None = None
    frame_peak_url: str | None = None
    identifications: list[IdentificationRead] = Field(default_factory=list)
    item_record: ItemRecordRead | None = None
    options: list[OptionScoreRead] = Field(default_factory=list)
    entries: list[JournalEntryRead] = Field(default_factory=list)
    corrections: list[CorrectionRead] = Field(default_factory=list)


class VoidResponse(ApiModel):
    event_id: int
    status: EventStatus
    reversing_entry_ids: list[int] = Field(default_factory=list)


class CorrectionCreate(ApiModel):
    """The ask answer and the dashboard override. Free text lands here and stops here."""

    event_id: int
    label: ValidatedLabel
    item_class: ItemClass | None = Field(default=None, alias="class")
    by: str = Field(default="person", max_length=40)


class CorrectionResponse(ApiModel):
    event_id: int
    label: str
    item_class: ItemClass | None = Field(default=None, alias="class")
    correction_id: int
    status: EventStatus


class AssetRead(ApiModel):
    id: int
    tag: str
    description: str
    category: str | None = None
    cost_cents: int
    in_service_date: str
    book_life_months: int
    salvage_cents: int = 0
    tax_method: TaxMethod
    tax_basis_cents_override: int | None = None
    status: AssetStatus
    disposed_event_id: int | None = None
    insured: bool = False
    location: str | None = None
    book_value_cents: int | None = None
    tax_basis_cents: int | None = None


class AssetCreate(ApiModel):
    tag: ValidatedLabel
    description: str = Field(max_length=120)
    category: ValidatedLabel | None = None
    cost_cents: int = Field(ge=0)
    in_service_date: str = Field(max_length=32)
    book_life_months: int = Field(gt=0)
    salvage_cents: int = Field(default=0, ge=0)
    tax_method: TaxMethod = TaxMethod.straight_line
    tax_basis_cents_override: int | None = None
    insured: bool = False
    location: str | None = Field(default=None, max_length=80)


class AssetUpdate(ApiModel):
    description: str | None = Field(default=None, max_length=120)
    category: ValidatedLabel | None = None
    cost_cents: int | None = Field(default=None, ge=0)
    in_service_date: str | None = Field(default=None, max_length=32)
    book_life_months: int | None = Field(default=None, gt=0)
    salvage_cents: int | None = Field(default=None, ge=0)
    tax_method: TaxMethod | None = None
    tax_basis_cents_override: int | None = None
    status: AssetStatus | None = None
    insured: bool | None = None
    location: str | None = Field(default=None, max_length=80)


class AssetListResponse(ApiModel):
    assets: list[AssetRead] = Field(default_factory=list)


class CatalogItemRead(ApiModel):
    id: int
    label: str
    item_class: ItemClass = Field(alias="class")
    unit_cost_cents: int | None = None
    unit_mass_g: float | None = None
    price_per_kg_cents: int | None = None
    fmv_per_kg_cents: int | None = None
    material_mix: dict[str, float] = Field(default_factory=dict)
    regulatory_flags: list[str] = Field(default_factory=list)
    mass_prior_mean_g: float | None = None
    mass_prior_var: float | None = None
    mass_prior_n: int = 0


class CatalogItemCreate(ApiModel):
    label: ValidatedLabel
    item_class: ItemClass = Field(alias="class")
    unit_cost_cents: int | None = Field(default=None, ge=0)
    unit_mass_g: float | None = Field(default=None, gt=0)
    price_per_kg_cents: int | None = Field(default=None, ge=0)
    fmv_per_kg_cents: int | None = Field(default=None, ge=0)
    material_mix: dict[MaterialKey, float] = Field(default_factory=dict)
    regulatory_flags: list[MaterialKey] = Field(default_factory=list, max_length=8)


class CatalogListResponse(ApiModel):
    items: list[CatalogItemRead] = Field(default_factory=list)


class TrialBalanceRow(ApiModel):
    account: str
    account_name: str
    debit_cents: int = 0
    credit_cents: int = 0


class JournalResponse(ApiModel):
    basis: JournalBasis | None = None
    entries: list[JournalEntryRead] = Field(default_factory=list)
    trial_balance: list[TrialBalanceRow] = Field(default_factory=list)
    balanced: bool = True


class RoundRead(ApiModel):
    id: int
    started_at: str
    ended_at: str | None = None
    n_events: int = 0
    n_correct_first_try: int = 0
    n_asked: int = 0
    n_corrected_after_confident: int = 0
    mean_latency_ms: float | None = None
    cloud_cost_microusd: int = 0
    first_try_accuracy: float | None = None
    ask_rate: float | None = None
    cost_per_event_microusd: float | None = None
    local_share: float | None = None


class RoundListResponse(ApiModel):
    rounds: list[RoundRead] = Field(default_factory=list)
    learned: list[str] = Field(
        default_factory=list,
        description="The most recent corrections in plain words, newest first.",
    )


class SummaryResponse(ApiModel):
    """The four header numbers on the Live page."""

    saved_if_followed_cents: int = 0
    kg_diverted: float = 0.0
    events: int = 0
    first_try_accuracy: float | None = None


class CloseCheck(ApiModel):
    id: str
    title: str
    result: Literal["pass", "warn", "fail"]
    detail: str = ""
    numbers: dict[str, float] = Field(default_factory=dict)


class CloseRequest(ApiModel):
    period_start: str = Field(max_length=32)
    period_end: str = Field(max_length=32)


class CloseRead(ApiModel):
    id: int
    period_start: str
    period_end: str
    created_at: str
    status: str
    totals: dict[str, Any] = Field(default_factory=dict)
    checks: list[CloseCheck] = Field(default_factory=list)
    investigation_md: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)
    # Lane P. The four depth blocks a CFO reads. They are defined at the end of this
    # file, so CloseRead is rebuilt down there once they exist.
    rollforward: RollforwardBlock | None = None
    reconciliation: ReconciliationBlock | None = None
    form4797: Form4797Block | None = None
    memo_md: str | None = None
    investigation_steps: list[ToolStep] = Field(default_factory=list)


class RuleRead(ApiModel):
    """One tax rule as the evidence drawer shows it.

    The words and the link come from `tax_rules.yaml`, which is the only copy of either.
    DESIGN.md 4.2 asks the drawer for the rule in plain language with its citation as a link,
    so retyping the text into a client would be a second copy that drifts.
    """

    id: str
    title: str
    plain_text: str
    citation_url: str | None = None
    needs_human_review: bool = False


class RulesResponse(ApiModel):
    rules: list[RuleRead] = Field(default_factory=list)


class SettingsRead(ApiModel):
    """Only the keys /api/settings may change. Nothing here is a secret."""

    tax_rate: float
    capitalization_threshold_cents: int
    disposal_fee_cents: int
    recycle_fee_cents: int
    tone_co2e_kg: float
    speak_up_cents: int = 100
    step_min_g: float
    settle_ms: int
    bag_change_g: float
    confident_p: float
    min_margin: float
    memory_max_dist: float
    round_size: int
    llm_timeout_s: float
    # Added after the first real run, so they carry a default and an older client that does
    # not know them still validates.
    llm_service_tier: ServiceTier = "fast"
    llm_vision_effort: ReasoningEffort = "none"
    llm_text_effort: ReasoningEffort = "none"
    llm_estimate_effort: ReasoningEffort = "low"


class SettingsUpdate(ApiModel):
    tax_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    capitalization_threshold_cents: int | None = Field(default=None, ge=0)
    disposal_fee_cents: int | None = Field(default=None, ge=0)
    recycle_fee_cents: int | None = Field(default=None, ge=0)
    tone_co2e_kg: float | None = Field(default=None, ge=0.0)
    speak_up_cents: int | None = Field(default=None, ge=0)
    step_min_g: float | None = Field(default=None, gt=0.0)
    settle_ms: int | None = Field(default=None, gt=0)
    bag_change_g: float | None = Field(default=None, gt=0.0)
    confident_p: float | None = Field(default=None, ge=0.0, le=1.0)
    min_margin: float | None = Field(default=None, ge=0.0, le=1.0)
    memory_max_dist: float | None = Field(default=None, ge=0.0, le=2.0)
    round_size: int | None = Field(default=None, gt=0)
    llm_timeout_s: float | None = Field(default=None, gt=0.0)
    llm_service_tier: ServiceTier | None = None
    llm_vision_effort: ReasoningEffort | None = None
    llm_text_effort: ReasoningEffort | None = None
    llm_estimate_effort: ReasoningEffort | None = None


class DeviceTareResponse(ApiModel):
    sent: bool
    device: Literal["bin"] = "bin"


class SimTossRequest(ApiModel):
    """Dev only. Mounted only when DEV_TOOLS is on.

    With no `image` the frames come from whatever the camera is looking at right now, so
    the Add button on the dashboard and the phone can make a ticket out of a real item and
    a weight somebody typed in. With an `image` it is the old simulator path.
    """

    mass_g: float = Field(gt=0.0)
    label: ValidatedLabel | None = None
    image: str | None = Field(default=None, max_length=255)


class SimTossResponse(ApiModel):
    event_id: int
    status: EventStatus


class SimExpectRequest(ApiModel):
    """Dev only. Tells the stub identification provider what the simulator is about to toss."""

    label: ValidatedLabel
    mass_g: float | None = Field(default=None, gt=0.0)


class SimExpectResponse(ApiModel):
    label: str
    mass_g: float | None = None


class SetupResponse(ApiModel):
    """The setup checklist: every seed cell a person still has to fill in.

    PLAN.md section 17. One line per cell, so nothing fake can slip into the demo
    unnoticed. An empty list means the seed files are complete.
    """

    items: list[str] = Field(default_factory=list)


class ErrorResponse(ApiModel):
    detail: str
    code: str = "error"


UiEventCreated.model_rebuild()
UiEventUpdated.model_rebuild()
UiJournalPosted.model_rebuild()
UiMetricsUpdated.model_rebuild()


# Lane P, the review queue and the depth blocks on the close (PLAN.md 21a item 39) ------
# Appended at the end of the file on purpose, so two lanes editing this file at once do
# not land on the same lines.

REVIEW_NOTE_MAX = 240
DECIDED_BY_MAX = 40


class ToolStep(ApiModel):
    """One lookup an agent made, and what it found. This is the working, shown."""

    tool: str = Field(default="", max_length=40)
    args_summary: str = Field(default="", max_length=120)
    finding: str = Field(default="", max_length=240)


class ReviewProposal(ApiModel):
    """What the review agent thinks, and how it got there. It never acts on this."""

    decision: Literal["approve", "reject", "ask_person"] = "ask_person"
    reason: str = Field(default="", max_length=REVIEW_NOTE_MAX)
    evidence: list[str] = Field(default_factory=list)
    steps: list[ToolStep] = Field(default_factory=list)
    downgraded_reason: str | None = Field(default=None, max_length=REVIEW_NOTE_MAX)
    provider: str = ""
    model: str = ""
    tool_calls: int = 0
    latency_ms: int | None = None


class ReviewItemRead(ApiModel):
    """One open question, as the Review tab lists it."""

    id: int
    kind: ReviewKind
    status: ReviewStatus
    event_id: int
    label: str | None = None
    asset_id: int | None = None
    asset_tag: str | None = None
    amount_cents: int = 0
    reason: str = ""
    decided_by: str | None = None
    decided_at: str | None = None
    note: str | None = None
    created_at: str = ""
    # An unresolved ask carries what the bin was asking, so a person can answer it from
    # the queue instead of going to find the ticket.
    candidates: list[AskCandidate] = Field(default_factory=list)
    proposal: ReviewProposal | None = None
    agreed_with_agent: bool | None = None


class ReviewListResponse(ApiModel):
    items: list[ReviewItemRead] = Field(default_factory=list)
    open_count: int = 0


class ReviewDecision(ApiModel):
    """Who decided and why. Both fields are outside text, so both are cleaned."""

    by: str = Field(default="person", max_length=DECIDED_BY_MAX)
    note: str = Field(default="", max_length=REVIEW_NOTE_MAX)

    @field_validator("by", mode="before")
    @classmethod
    def _clean_by(cls, value: Any) -> Any:
        cleaned = _clean_free_text(value, DECIDED_BY_MAX)
        return cleaned or "person" if isinstance(cleaned, str) else cleaned

    @field_validator("note", mode="before")
    @classmethod
    def _clean_note(cls, value: Any) -> Any:
        return _clean_free_text(value, REVIEW_NOTE_MAX)


class ReviewDecisionResponse(ApiModel):
    """What the decision did: the item as it now stands, and what it moved."""

    item: ReviewItemRead
    reversing_entry_ids: list[int] = Field(default_factory=list)
    difference_cents: int = 0
    detail: str = ""
    agreed_with_agent: bool | None = None


class ReviewRunResponse(ApiModel):
    """What one run of the review agent produced."""

    proposed: int = 0
    items: list[ReviewItemRead] = Field(default_factory=list)


class RollforwardRow(ApiModel):
    """One asset's movement through the period, cost and accumulated depreciation."""

    asset_id: int | None = None
    tag: str = ""
    description: str = ""
    opening_cost_cents: int = 0
    additions_cents: int = 0
    disposals_cost_cents: int = 0
    closing_cost_cents: int = 0
    opening_accum_cents: int = 0
    depreciation_cents: int = 0
    disposals_accum_cents: int = 0
    closing_accum_cents: int = 0
    opening_nbv_cents: int = 0
    closing_nbv_cents: int = 0


class RollforwardBlock(ApiModel):
    period_start: str = ""
    period_end: str = ""
    rows: list[RollforwardRow] = Field(default_factory=list)
    total: RollforwardRow = Field(default_factory=RollforwardRow)
    ties: bool = True


class ReconciliationRow(ApiModel):
    """One disposed asset, book against tax, with the reason for the gap."""

    event_id: int
    asset_id: int | None = None
    tag: str = ""
    description: str = ""
    book_loss_cents: int = 0
    tax_loss_cents: int = 0
    difference_cents: int = 0
    reason: str = ""
    rule_ids: list[str] = Field(default_factory=list)


class ReconciliationBlock(ApiModel):
    """The M-1 shape: book loss, less the differences, equals the tax loss."""

    rows: list[ReconciliationRow] = Field(default_factory=list)
    book_loss_cents: int = 0
    differences_cents: int = 0
    tax_loss_cents: int = 0
    ties: bool = True
    title: str = ""


class Form4797Row(ApiModel):
    description: str = ""
    date_acquired: str = ""
    date_disposed: str = ""
    gross_proceeds_cents: int = 0
    cost_cents: int = 0
    depreciation_allowed_cents: int = 0
    gain_or_loss_cents: int = 0
    part: Literal["II", "III"] = "II"
    line: str = ""
    rule_ids: list[str] = Field(default_factory=list)
    recapture_note: str = ""


class Form4797Block(ApiModel):
    part_ii_rows: list[Form4797Row] = Field(default_factory=list)
    part_iii_rows: list[Form4797Row] = Field(default_factory=list)
    part_ii_line_10_cents: int = 0
    part_iii_recapture_cents: int = 0
    disclaimer: str = ""


class CategoryStat(ApiModel):
    category: Literal["food", "packaging", "equipment", "e-waste", "other"]
    tosses: int = 0
    cents: int = 0
    kg: float = 0.0


class StatsBucket(ApiModel):
    """One day or one week of tickets, totalled."""

    start: str
    tosses: int = 0
    wasted_cents: int = 0
    book_loss_cents: int = 0
    estimated_value_cents: int = 0
    kg_landfill: float = 0.0
    kg_co2e_avoided: float = 0.0
    asks: int = 0
    first_try_accuracy: float | None = None
    by_category: list[CategoryStat] = Field(default_factory=list)


class StatsAverages(ApiModel):
    days: float = 0.0
    tosses_per_day: float = 0.0
    wasted_cents_per_day: float = 0.0
    kg_per_day: float = 0.0


class StatsResponse(ApiModel):
    """What the bin saw over a range, by day or by week."""

    bucket: Literal["day", "week"] = "day"
    period_start: str = ""
    period_end: str = ""
    buckets: list[StatsBucket] = Field(default_factory=list)
    averages: StatsAverages = Field(default_factory=StatsAverages)
    suggestions: list[str] = Field(default_factory=list)
    summary_md: str | None = None


# CloseRead points forward at the three blocks above, so it is resolved here.
CloseRead.model_rebuild()
