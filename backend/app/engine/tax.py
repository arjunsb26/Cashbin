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
    sense = makes_no_sense(option, record, settings)
    if sense is not None:
        # PLAN.md 21a item 48. The user's words: it should not recommend stupid shit. The
        # option stays on the ticket with the reason it was dropped, because a person
        # reading the drawer should see what was considered and why it lost.
        return effect.model_copy(
            update={"allowed": False, "blocked_reason": sense}
        )
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


# What a thing has to be worth before selling or giving it away is worth anybody's time.
MIN_WORTH_SELLING_CENTS = 500
# And what it has to cost new before repairing it beats buying another one.
MIN_WORTH_REPAIRING_CENTS = 2_000
# A repair that costs more than this share of a replacement is not a repair, it is a
# slower way of buying one.
REPAIR_SHARE_OF_REPLACEMENT = 0.6

PACKAGING_MATERIALS_PREFIXES = ("mixed_paper", "corrugated", "mixed_plastics", "glass")

TOO_CHEAP_TO_SELL = "It is worth under 5 dollars."
TOO_CHEAP_TO_GIVE = "It is worth under 5 dollars."
BROKEN_NOT_SELLABLE = "It is broken."
NOT_WORTH_REPAIRING = "A new one costs under 20 dollars."
REPAIR_COSTS_TOO_MUCH = "Repair costs more than most of replacing it."
NOT_BROKEN_TO_REPAIR = "Nothing about it is broken."
FOOD_NOT_SEALED = "Opened food cannot be donated."
NOTHING_RECYCLES = "Nothing in it has a recycling route."
PACKAGING_NOT_GOODS = "Packaging is not worth selling."


def _is_packaging(record: ItemRecord) -> bool:
    """Paper, card, plastic or glass and no food. A box is not a thing anybody resells."""
    if not record.material_mix or is_food_item(record):
        return False
    return all(
        material.startswith(PACKAGING_MATERIALS_PREFIXES)
        for material in record.material_mix
    )


def _looks_sealed(record: ItemRecord) -> bool:
    """Whether anybody said this food is still shut. Nothing is assumed either way."""
    words = f"{record.detail} {record.description}".lower()
    return "sealed" in words or "unopened" in words


def makes_no_sense(
    option: Option, record: ItemRecord, settings: EngineSettings
) -> str | None:
    """Why this option is not a real answer for this item, or None when it is.

    PLAN.md 21a item 48. Every one of these is something the engine used to offer with a
    straight face: reselling a bagel, repairing a nine dollar charger, donating half a
    sandwich somebody had already started, recycling something with no recycling route.
    """
    broken = record.condition is Condition.broken
    fmv = record.fmv_mid or 0
    replacement = record.replacement_cents or 0
    repair = record.repair_mid

    if option is Option.resell:
        if is_food_item(record):
            # Food has its own rule and its own words, and it says more than this one.
            return None
        if _is_packaging(record):
            return PACKAGING_NOT_GOODS
        if broken:
            return BROKEN_NOT_SELLABLE
        if fmv < MIN_WORTH_SELLING_CENTS:
            return TOO_CHEAP_TO_SELL

    if option is Option.donate:
        if is_food_item(record):
            return None if _looks_sealed(record) else FOOD_NOT_SEALED
        if broken:
            return BROKEN_NOT_SELLABLE
        if fmv < MIN_WORTH_SELLING_CENTS:
            return TOO_CHEAP_TO_GIVE

    if option is Option.repair:
        if not broken:
            return NOT_BROKEN_TO_REPAIR
        if replacement < MIN_WORTH_REPAIRING_CENTS:
            return NOT_WORTH_REPAIRING
        if repair is not None and repair >= replacement * REPAIR_SHARE_OF_REPLACEMENT:
            return REPAIR_COSTS_TOO_MUCH

    if option is Option.recycle and not _recycles(record):
        return NOTHING_RECYCLES

    return None


def _recycles(record: ItemRecord) -> bool:
    """Does anything in this actually have somewhere to go?

    Food composts, which counts. Everything else needs a material the WARM table publishes
    a recycling factor for, otherwise "recycle it" is a word with nothing behind it.
    """
    from app.engine import carbon

    if not record.material_mix:
        return False
    for material in record.material_mix:
        if carbon.is_food_material(material):
            if carbon.factor(material, carbon.Fate.compost) is not None:
                return True
            continue
        if carbon.factor(material, carbon.Fate.recycle) is not None:
            return True
    return False


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
