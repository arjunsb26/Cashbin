"""The tax cell for every option and every class, from PLAN.md section 10.

One pure function per cell of that table. Nothing here reads the database, and
nothing here invents a number: a figure the record does not carry means the
option is not offered rather than priced at zero.

Sign convention, from the point of view of the business:

- `cash_cents` is money in, so a fee is negative and a sale is positive.
- `tax_effect_cents` is the change in cash from tax, so a deduction is positive
  and tax owed on a gain is negative.
- `net_after_tax_cents` on the option row adds the two, plus the replacement
  cost a repair avoids.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.engine import carbon
from app.engine.records import (
    AssetInfo,
    Condition,
    EngineSettings,
    ItemClass,
    ItemRecord,
    Option,
    TaxMethod,
)

# The exact sentence a person sees when electronics cannot go in the bin.
EWASTE_BLOCKED_REASON = "Electronics: check your state's disposal rule"

# The exact sentence a person sees on the blocked resale row for food.
FOOD_NO_RESALE_REASON = "Food in the bin cannot be resold"

BLOCKING_FLAGS = ("electronics", "battery")

FOOD_FLAG = "food"


class TaxEffect(BaseModel):
    """What one option does to cash and to the tax bill."""

    model_config = ConfigDict(frozen=True)

    cash_cents: int = 0
    tax_effect_cents: int = 0
    deduction_cents: int = 0
    gain_cents: int = 0
    rule_ids: tuple[str, ...] = Field(default_factory=tuple)
    needs_human_review: bool = False
    notes: tuple[str, ...] = Field(default_factory=tuple)
    allowed: bool = True
    blocked_reason: str | None = None


class FoodDonation(BaseModel):
    """The two figures behind the enhanced deduction for donated food."""

    model_config = ConfigDict(frozen=True)

    enhanced_cents: int
    incremental_cents: int


def apply_rate(rate: float, cents: int) -> int:
    """Tax at `rate` on a figure in cents, rounded half up to whole cents."""
    value = Decimal(str(rate)) * Decimal(cents)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# PLAN.md 21a item 47. A model asked what a mouse is worth says 1173 cents, and 11.73 on a
# bin reads as a number somebody measured rather than a number somebody estimated. These
# are the steps a person uses out loud: fifty cents up to twenty dollars, a dollar to a
# hundred, five dollars to a thousand, ten above that.
MONEY_STEPS: tuple[tuple[int, int], ...] = (
    (2_000, 50),
    (10_000, 100),
    (100_000, 500),
)
MONEY_STEP_ABOVE = 1_000


def round_money(cents: int | None) -> int | None:
    """One estimate, rounded to a figure a person would actually say.

    Only the middle of a range is rounded. The low and the high keep every cent, because
    the drawer draws the range and a rounded range would be a claim about precision that
    nobody made.
    """
    if cents is None:
        return None
    size = abs(cents)
    step = MONEY_STEP_ABOVE
    for ceiling, candidate in MONEY_STEPS:
        if size < ceiling:
            step = candidate
            break
    sign = -1 if cents < 0 else 1
    return sign * int(round(size / step) * step)


def money(cents: int) -> str:
    """Cents as a plain dollar figure for a note a person reads."""
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{part:02d}"


def is_blocked(record: ItemRecord) -> bool:
    """True when the item carries a flag that keeps it out of the landfill."""
    return any(record.has_flag(flag) for flag in BLOCKING_FLAGS)


def is_food_item(record: ItemRecord) -> bool:
    """True for anything the catalog calls food or whose mass is mostly organics."""
    return record.has_flag(FOOD_FLAG) or carbon.is_food(record)


def food_donation_deduction(cost_basis_cents: int, fmv_cents: int) -> FoodDonation:
    """IRC 170(e)(3): cost plus half the mark up, capped at twice cost."""
    markup = max(fmv_cents - cost_basis_cents, 0)
    enhanced = min(cost_basis_cents + markup // 2, 2 * cost_basis_cents)
    return FoodDonation(
        enhanced_cents=enhanced,
        incremental_cents=enhanced - cost_basis_cents,
    )


def _bonus_note(asset: AssetInfo | None) -> tuple[list[str], list[str]]:
    """Extra notes and rule ids when an asset was fully expensed on day one."""
    if asset is not None and asset.tax_method is TaxMethod.bonus_100:
        return (
            ["This asset was written off in full when it was bought, so no basis is left."],
            ["BONUS_100"],
        )
    return ([], [])


# --- trash -------------------------------------------------------------------


def trash_fixed_asset(
    record: ItemRecord, settings: EngineSettings, asset: AssetInfo | None = None
) -> TaxEffect:
    notes, rules = _bonus_note(asset)
    deduction = record.tax_basis_cents
    return TaxEffect(
        cash_cents=-settings.disposal_fee_cents,
        tax_effect_cents=apply_rate(settings.tax_rate, deduction),
        deduction_cents=deduction,
        rule_ids=("ABANDON", *rules),
        notes=(
            f"Abandoning this leaves a deduction of {money(deduction)}.",
            *notes,
        ),
    )


def trash_inventory(record: ItemRecord, settings: EngineSettings) -> TaxEffect:
    return TaxEffect(
        cash_cents=-settings.disposal_fee_cents,
        rule_ids=("INV_COGS",),
        notes=("The cost is already in cost of goods sold, so there is no extra deduction.",),
    )


def trash_untracked(record: ItemRecord, settings: EngineSettings) -> TaxEffect:
    return TaxEffect(cash_cents=-settings.disposal_fee_cents)


# --- recycle -----------------------------------------------------------------


def _scrap_cash(record: ItemRecord, settings: EngineSettings) -> int:
    return (record.scrap_cents or 0) - settings.recycle_fee_cents


def recycle_fixed_asset(
    record: ItemRecord, settings: EngineSettings, asset: AssetInfo | None = None
) -> TaxEffect:
    base = trash_fixed_asset(record, settings, asset)
    return base.model_copy(update={"cash_cents": _scrap_cash(record, settings)})


def recycle_inventory(record: ItemRecord, settings: EngineSettings) -> TaxEffect:
    base = trash_inventory(record, settings)
    return base.model_copy(update={"cash_cents": _scrap_cash(record, settings)})


def recycle_untracked(record: ItemRecord, settings: EngineSettings) -> TaxEffect:
    return TaxEffect(cash_cents=_scrap_cash(record, settings))


# --- resell ------------------------------------------------------------------


def resell_fixed_asset(
    record: ItemRecord, settings: EngineSettings, asset: AssetInfo | None = None
) -> TaxEffect | None:
    if record.fmv_mid is None:
        return None
    gain = record.fmv_mid - record.tax_basis_cents
    notes = [f"Sale price {money(record.fmv_mid)} against a tax basis of "
             f"{money(record.tax_basis_cents)}."]
    if gain > 0:
        notes.append(
            "The gain is taxed as ordinary income up to the depreciation already taken."
        )
    return TaxEffect(
        cash_cents=record.fmv_mid,
        tax_effect_cents=-apply_rate(settings.tax_rate, gain),
        gain_cents=gain,
        rule_ids=("RECAPTURE",),
        notes=tuple(notes),
    )


def resell_inventory(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    if record.fmv_mid is None or record.cost_basis_cents is None:
        return None
    gain = record.fmv_mid - record.cost_basis_cents
    return TaxEffect(
        cash_cents=record.fmv_mid,
        tax_effect_cents=-apply_rate(settings.tax_rate, gain),
        gain_cents=gain,
        notes=(
            f"Sale price {money(record.fmv_mid)} against a cost of "
            f"{money(record.cost_basis_cents)}.",
        ),
    )


def resell_untracked(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    if record.fmv_mid is None:
        return None
    return TaxEffect(
        cash_cents=record.fmv_mid,
        tax_effect_cents=-apply_rate(settings.tax_rate, record.fmv_mid),
        gain_cents=record.fmv_mid,
        needs_human_review=True,
        notes=(
            "Nothing on the books records what this cost, so the whole sale price is "
            "treated as gain until a person says otherwise.",
        ),
    )


# --- donate ------------------------------------------------------------------


def donate_fixed_asset(
    record: ItemRecord, settings: EngineSettings, asset: AssetInfo | None = None
) -> TaxEffect | None:
    if record.fmv_mid is None:
        return None
    deduction = min(record.fmv_mid, record.tax_basis_cents)
    return TaxEffect(
        cash_cents=0,
        tax_effect_cents=apply_rate(settings.tax_rate, deduction),
        deduction_cents=deduction,
        rule_ids=("DONATE_EQUIP",),
        needs_human_review=True,
        notes=(
            f"Deduction taken as the lower of value {money(record.fmv_mid)} and basis "
            f"{money(record.tax_basis_cents)}.",
        ),
    )


def donate_inventory(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    """Offered for food only, because the enhanced deduction is a food rule."""
    if not carbon.is_food(record):
        return None
    if record.fmv_mid is None or record.cost_basis_cents is None:
        return None
    result = food_donation_deduction(record.cost_basis_cents, record.fmv_mid)
    return TaxEffect(
        cash_cents=0,
        tax_effect_cents=apply_rate(settings.tax_rate, result.incremental_cents),
        deduction_cents=result.incremental_cents,
        rule_ids=("DONATE_FOOD",),
        needs_human_review=True,
        notes=(
            f"Cost {money(record.cost_basis_cents)}, value {money(record.fmv_mid)}, "
            f"enhanced deduction {money(result.enhanced_cents)}, "
            f"{money(result.incremental_cents)} more than cost.",
        ),
    )


def donate_untracked(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    return None


# --- repair ------------------------------------------------------------------


def _repair_offered(record: ItemRecord) -> bool:
    """PLAN.md 21a item 17.

    A thing somebody watched break is worth repairing whatever the quote says. A thing
    nobody is sure about is worth repairing only when the repair comes in under half a new
    one, because otherwise every nine dollar charger comes back as "repair it" and the bin
    stops being believable.
    """
    if record.repair_mid is None or record.replacement_cents is None:
        return False
    if record.condition is Condition.broken:
        return True
    if record.condition is Condition.unknown:
        return record.repair_mid * 2 < record.replacement_cents
    return False


def repair_fixed_asset(
    record: ItemRecord, settings: EngineSettings, asset: AssetInfo | None = None
) -> TaxEffect | None:
    if not _repair_offered(record) or record.repair_mid is None:
        return None
    return TaxEffect(
        cash_cents=-record.repair_mid,
        notes=(
            f"Repair costs {money(record.repair_mid)} and the asset stays on the register.",
        ),
    )


def repair_inventory(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    return None


def repair_untracked(record: ItemRecord, settings: EngineSettings) -> TaxEffect | None:
    if not _repair_offered(record) or record.repair_mid is None:
        return None
    return TaxEffect(
        cash_cents=-record.repair_mid,
        notes=(f"Repair costs {money(record.repair_mid)}.",),
    )


# --- the table ---------------------------------------------------------------


def tax_effect_for(
    option: Option,
    record: ItemRecord,
    settings: EngineSettings,
    asset: AssetInfo | None = None,
) -> TaxEffect | None:
    """The cell of the section 10 table for this option and this class.

    `None` means the table does not offer this option for this class, or the
    record is missing a figure the option needs. A blocked option still comes
    back, with `allowed` false, because a person should see why it is blocked.
    """
    effect = _dispatch(option, record, settings, asset)
    if effect is None:
        return None
    if option is Option.trash and is_blocked(record):
        return effect.model_copy(
            update={
                "allowed": False,
                "blocked_reason": EWASTE_BLOCKED_REASON,
                "rule_ids": (*effect.rule_ids, "EWASTE"),
            }
        )
    if option is Option.resell and is_food_item(record):
        return effect.model_copy(
            update={
                "allowed": False,
                "blocked_reason": FOOD_NO_RESALE_REASON,
                "rule_ids": (*effect.rule_ids, "FOOD_NO_RESALE"),
            }
        )
    return effect


def _dispatch(
    option: Option,
    record: ItemRecord,
    settings: EngineSettings,
    asset: AssetInfo | None,
) -> TaxEffect | None:
    cls = record.item_class
    if option is Option.trash:
        if cls is ItemClass.fixed_asset:
            return trash_fixed_asset(record, settings, asset)
        if cls is ItemClass.inventory:
            return trash_inventory(record, settings)
        return trash_untracked(record, settings)
    if option is Option.recycle:
        if cls is ItemClass.fixed_asset:
            return recycle_fixed_asset(record, settings, asset)
        if cls is ItemClass.inventory:
            return recycle_inventory(record, settings)
        return recycle_untracked(record, settings)
    if option is Option.resell:
        if cls is ItemClass.fixed_asset:
            return resell_fixed_asset(record, settings, asset)
        if cls is ItemClass.inventory:
            return resell_inventory(record, settings)
        return resell_untracked(record, settings)
    if option is Option.donate:
        if cls is ItemClass.fixed_asset:
            return donate_fixed_asset(record, settings, asset)
        if cls is ItemClass.inventory:
            return donate_inventory(record, settings)
        return donate_untracked(record, settings)
    if cls is ItemClass.fixed_asset:
        return repair_fixed_asset(record, settings, asset)
    if cls is ItemClass.inventory:
        return repair_inventory(record, settings)
    return repair_untracked(record, settings)
