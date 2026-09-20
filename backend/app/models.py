"""SQL tables from PLAN.md section 8.

Money is integer cents, mass is float grams, timestamps are UTC ISO strings.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now_iso() -> str:
    """Timestamps are stored as UTC ISO strings, as PLAN.md section 8 requires."""
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


# Enums ---------------------------------------------------------------------


class ItemClass(enum.StrEnum):
    inventory = "inventory"
    fixed_asset = "fixed_asset"
    untracked = "untracked"


class TaxMethod(enum.StrEnum):
    bonus_100 = "bonus_100"
    straight_line = "straight_line"


class AssetStatus(enum.StrEnum):
    active = "active"
    disposed = "disposed"
    ghost_suspected = "ghost_suspected"


class EventKind(enum.StrEnum):
    toss = "toss"
    bag_change = "bag_change"
    removal = "removal"


class EventStatus(enum.StrEnum):
    detected = "detected"
    identified = "identified"
    asking = "asking"
    confirmed = "confirmed"
    posted = "posted"
    void = "void"


class IdentifyMethod(enum.StrEnum):
    qr = "qr"
    memory = "memory"
    cloud = "cloud"
    human = "human"
    stub = "stub"


class OptionKind(enum.StrEnum):
    trash = "trash"
    recycle = "recycle"
    repair = "repair"
    resell = "resell"
    donate = "donate"


class JournalBasis(enum.StrEnum):
    book = "book"
    tax_memo = "tax_memo"


class CropQuality(enum.StrEnum):
    ok = "ok"
    low = "low"


class ReviewKind(enum.StrEnum):
    """Why a ticket landed in the review queue. Lane P, PLAN.md 21a item 39."""

    donation = "donation"
    estimate_above_threshold = "estimate_above_threshold"
    possible_unrecorded_asset = "possible_unrecorded_asset"
    unresolved_ask = "unresolved_ask"
    confident_overruled = "confident_overruled"


class ReviewStatus(enum.StrEnum):
    open = "open"
    approved = "approved"
    rejected = "rejected"


def _enum(python_enum: type[enum.Enum], name: str) -> SAEnum:
    """Store enum values, not member names, so the DB text matches the wire text."""
    return SAEnum(python_enum, name=name, values_callable=lambda e: [m.value for m in e])


# Chart of accounts ---------------------------------------------------------

CHART_OF_ACCOUNTS: dict[str, str] = {
    "1200": "Inventory",
    "1500": "Fixed Assets",
    "1590": "Accumulated Depreciation",
    "1000": "Cash",
    "5100": "Waste and Shrink Expense",
    "7200": "Loss on Disposal of Assets",
    "7210": "Gain on Disposal of Assets",
    "6400": "Repairs and Maintenance",
    "6800": "Charitable Contributions",
}

ACCOUNT_INVENTORY = "1200"
ACCOUNT_FIXED_ASSETS = "1500"
ACCOUNT_ACCUMULATED_DEPRECIATION = "1590"
ACCOUNT_CASH = "1000"
ACCOUNT_WASTE_EXPENSE = "5100"
ACCOUNT_LOSS_ON_DISPOSAL = "7200"
ACCOUNT_GAIN_ON_DISPOSAL = "7210"
ACCOUNT_REPAIRS = "6400"
ACCOUNT_CHARITABLE = "6800"


# Tables --------------------------------------------------------------------


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)


class CatalogItem(Base):
    __tablename__ = "catalog_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    item_class: Mapped[ItemClass] = mapped_column(
        "class", _enum(ItemClass, "item_class"), nullable=False
    )
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)
    unit_mass_g: Mapped[float | None] = mapped_column(Float)
    price_per_kg_cents: Mapped[int | None] = mapped_column(Integer)
    fmv_per_kg_cents: Mapped[int | None] = mapped_column(Integer)
    material_mix_json: Mapped[str | None] = mapped_column(Text)
    regulatory_flags_json: Mapped[str | None] = mapped_column(Text)
    mass_prior_mean_g: Mapped[float | None] = mapped_column(Float)
    mass_prior_var: Mapped[float | None] = mapped_column(Float)
    mass_prior_n: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str | None] = mapped_column(String(40))
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    in_service_date: Mapped[str] = mapped_column(String(32), nullable=False)
    book_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    salvage_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_method: Mapped[TaxMethod] = mapped_column(_enum(TaxMethod, "tax_method"), nullable=False)
    tax_basis_cents_override: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[AssetStatus] = mapped_column(
        _enum(AssetStatus, "asset_status"), nullable=False, default=AssetStatus.active
    )
    disposed_event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"))
    insured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(String(80))


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    kind: Mapped[EventKind] = mapped_column(_enum(EventKind, "event_kind"), nullable=False)
    mass_g: Mapped[float | None] = mapped_column(Float)
    mass_err_g: Mapped[float | None] = mapped_column(Float)
    trace_json: Mapped[str | None] = mapped_column(Text)
    frame_before: Mapped[str | None] = mapped_column(String(255))
    frame_after: Mapped[str | None] = mapped_column(String(255))
    frame_peak: Mapped[str | None] = mapped_column(String(255))
    crop: Mapped[str | None] = mapped_column(String(255))
    crop_quality: Mapped[CropQuality | None] = mapped_column(_enum(CropQuality, "crop_quality"))
    status: Mapped[EventStatus] = mapped_column(
        _enum(EventStatus, "event_status"), nullable=False, default=EventStatus.detected
    )
    round_id: Mapped[int | None] = mapped_column(ForeignKey("round.id"))


class Identification(Base):
    __tablename__ = "identification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), nullable=False, index=True)
    method: Mapped[IdentifyMethod] = mapped_column(
        _enum(IdentifyMethod, "identify_method"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(40))
    item_class: Mapped[ItemClass | None] = mapped_column(
        "class", _enum(ItemClass, "item_class")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    candidates_json: Mapped[str | None] = mapped_column(Text)
    posterior_json: Mapped[str | None] = mapped_column(Text)
    used_mass_prior: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_microusd: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # CLAUDE.md: every identification row says which provider and model actually served it.
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))


class ItemRecord(Base):
    __tablename__ = "item_record"

    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), primary_key=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    item_class: Mapped[ItemClass] = mapped_column(
        "class", _enum(ItemClass, "item_class"), nullable=False
    )
    mass_g: Mapped[float] = mapped_column(Float, nullable=False)
    # The repair rule needs the item's condition. PLAN.md 21a item 8 added this column.
    condition: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    material_mix_json: Mapped[str | None] = mapped_column(Text)
    regulatory_flags_json: Mapped[str | None] = mapped_column(Text)
    book_value_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_basis_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"))
    cost_basis_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fmv_low: Mapped[int | None] = mapped_column(Integer)
    fmv_mid: Mapped[int | None] = mapped_column(Integer)
    fmv_high: Mapped[int | None] = mapped_column(Integer)
    fmv_source: Mapped[str | None] = mapped_column(String(24))
    repair_low: Mapped[int | None] = mapped_column(Integer)
    repair_mid: Mapped[int | None] = mapped_column(Integer)
    repair_high: Mapped[int | None] = mapped_column(Integer)
    repair_source: Mapped[str | None] = mapped_column(String(24))
    replacement_cents: Mapped[int | None] = mapped_column(Integer)
    replacement_source: Mapped[str | None] = mapped_column(String(24))
    scrap_cents: Mapped[int | None] = mapped_column(Integer)
    scrap_source: Mapped[str | None] = mapped_column(String(24))


class OptionScore(Base):
    __tablename__ = "option_score"
    __table_args__ = (UniqueConstraint("event_id", "option", name="uq_option_score_event_option"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), nullable=False, index=True)
    option: Mapped[OptionKind] = mapped_column(_enum(OptionKind, "option_kind"), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(160))
    cash_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_effect_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_after_tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kg_co2e: Mapped[float | None] = mapped_column(Float)
    kg_landfill: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes_json: Mapped[str | None] = mapped_column(Text)
    rule_ids_json: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)


class JournalEntry(Base):
    __tablename__ = "journal_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id"), index=True)
    close_id: Mapped[int | None] = mapped_column(ForeignKey("close.id"), index=True)
    posted_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    memo: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    basis: Mapped[JournalBasis] = mapped_column(
        _enum(JournalBasis, "journal_basis"), nullable=False, default=JournalBasis.book
    )
    evidence_json: Mapped[str | None] = mapped_column(Text)


class JournalLine(Base):
    __tablename__ = "journal_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entry.id"), nullable=False, index=True
    )
    account: Mapped[str] = mapped_column(String(8), nullable=False)
    debit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    credit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Correction(Base):
    __tablename__ = "correction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(40), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(200))
    new_value: Mapped[str | None] = mapped_column(String(200))
    by: Mapped[str] = mapped_column(String(40), nullable=False, default="person")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class Exemplar(Base):
    __tablename__ = "exemplar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mass_g: Mapped[float | None] = mapped_column(Float)
    confirmed_by: Mapped[str] = mapped_column(String(40), nullable=False, default="person")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)


class Round(Base):
    __tablename__ = "round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    ended_at: Mapped[str | None] = mapped_column(String(32))
    n_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_correct_first_try: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_asked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_corrected_after_confident: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean_latency_ms: Mapped[float | None] = mapped_column(Float)
    cloud_cost_microusd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Close(Base):
    __tablename__ = "close"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    totals_json: Mapped[str | None] = mapped_column(Text)
    checks_json: Mapped[str | None] = mapped_column(Text)
    investigation_md: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[str | None] = mapped_column(Text)


class ReviewItem(Base):
    """One thing a person has to approve or reject before the period is signed off.

    One row per event per kind, so the catch-up pass in the close can run as often
    as it likes without raising the same question twice.
    """

    __tablename__ = "review_item"
    __table_args__ = (UniqueConstraint("event_id", "kind", name="uq_review_item_event_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[ReviewKind] = mapped_column(_enum(ReviewKind, "review_kind"), nullable=False)
    # A ticket that is taken out of the books entirely takes its open questions with it,
    # so the queue can never point at a ticket that no longer exists.
    event_id: Mapped[int] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id", ondelete="SET NULL"))
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    status: Mapped[ReviewStatus] = mapped_column(
        _enum(ReviewStatus, "review_status"), nullable=False, default=ReviewStatus.open
    )
    decided_by: Mapped[str | None] = mapped_column(String(40))
    decided_at: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    # What the review agent proposed, and whether the person went along with it. The
    # proposal is never acted on: it sits here until a person decides.
    proposal_json: Mapped[str | None] = mapped_column(Text)
    agreed_with_agent: Mapped[bool | None] = mapped_column(Boolean)


ALL_TABLES: tuple[str, ...] = (
    "settings",
    "catalog_item",
    "asset",
    "event",
    "identification",
    "item_record",
    "option_score",
    "journal_entry",
    "journal_line",
    "correction",
    "exemplar",
    "round",
    "close",
    "review_item",
)
