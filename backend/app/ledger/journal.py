"""Journal entry builders, per PLAN.md section 11.

Every builder returns an entry that balances, and every builder checks that
before handing it back. An entry that does not balance raises rather than
posting, because a ledger that does not balance is worse than no ledger.

Nothing here writes to the database. The glue layer turns these objects into
`journal_entry` and `journal_line` rows.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.engine.records import AssetInfo, EngineSettings, ItemClass, ItemRecord
from app.engine.tax import TaxEffect, money


class Account(StrEnum):
    """The chart of accounts from PLAN.md section 8. Small and fixed."""

    inventory = "1200 Inventory"
    fixed_assets = "1500 Fixed Assets"
    accumulated_depreciation = "1590 Accumulated Depreciation"
    cash = "1000 Cash"
    waste_and_shrink = "5100 Waste and Shrink Expense"
    loss_on_disposal = "7200 Loss on Disposal of Assets"
    gain_on_disposal = "7210 Gain on Disposal of Assets"
    repairs_and_maintenance = "6400 Repairs and Maintenance"
    charitable_contributions = "6800 Charitable Contributions"


class Basis(StrEnum):
    book = "book"
    tax_memo = "tax_memo"


class Unbalanced(ValueError):  # noqa: N818
    """Raised when an entry's debits and credits do not agree."""


class JournalLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    account: Account
    debit_cents: int = 0
    credit_cents: int = 0


class JournalEntry(BaseModel):
    memo: str
    basis: Basis = Basis.book
    lines: list[JournalLine] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_debits_cents(self) -> int:
        return sum(line.debit_cents for line in self.lines)

    @property
    def total_credits_cents(self) -> int:
        return sum(line.credit_cents for line in self.lines)


def assert_balanced(entry: JournalEntry) -> JournalEntry:
    """Return the entry, or raise with both totals so the gap is obvious."""
    debits = entry.total_debits_cents
    credit_total = entry.total_credits_cents
    if debits != credit_total:
        raise Unbalanced(
            f"{entry.memo}: debits {money(debits)} do not equal credits {money(credit_total)}"
        )
    return entry


def _evidence(record: ItemRecord, **extra: Any) -> dict[str, Any]:
    """The audit trail carried on every entry."""
    base: dict[str, Any] = {
        "event_id": record.event_id,
        "label": record.label,
        "class": record.item_class.value,
        "mass_g": record.mass_g,
        "event_date": record.event_date.isoformat(),
        "asset_id": record.asset_id,
    }
    base.update(extra)
    return base


def inventory_toss(record: ItemRecord) -> JournalEntry | None:
    """Write off what was tossed. Dr waste and shrink, Cr inventory."""
    amount = record.cost_basis_cents
    if amount is None or amount <= 0:
        return None
    entry = JournalEntry(
        memo=f"Write off {record.label}",
        basis=Basis.book,
        lines=[
            JournalLine(account=Account.waste_and_shrink, debit_cents=amount),
            JournalLine(account=Account.inventory, credit_cents=amount),
        ],
        evidence=_evidence(record, cost_basis_cents=amount),
    )
    return assert_balanced(entry)


def fixed_asset_disposal(
    record: ItemRecord,
    asset: AssetInfo,
    proceeds_cents: int = 0,
) -> JournalEntry:
    """Take an asset off the register, with the gain or loss it leaves behind."""
    cost = asset.cost_cents or 0
    book = record.book_value_cents
    accum = cost - book
    gain = proceeds_cents - book

    lines: list[JournalLine] = []
    if accum:
        lines.append(
            JournalLine(account=Account.accumulated_depreciation, debit_cents=accum)
        )
    if proceeds_cents:
        lines.append(JournalLine(account=Account.cash, debit_cents=proceeds_cents))
    if gain < 0:
        lines.append(JournalLine(account=Account.loss_on_disposal, debit_cents=-gain))
    lines.append(JournalLine(account=Account.fixed_assets, credit_cents=cost))
    if gain > 0:
        lines.append(JournalLine(account=Account.gain_on_disposal, credit_cents=gain))

    entry = JournalEntry(
        memo=f"Dispose of {asset.description} ({asset.tag})",
        basis=Basis.book,
        lines=lines,
        evidence=_evidence(
            record,
            asset_tag=asset.tag,
            cost_cents=cost,
            accum_cents=accum,
            book_value_cents=book,
            proceeds_cents=proceeds_cents,
            gain_cents=gain,
        ),
    )
    return assert_balanced(entry)


def tax_memo(
    record: ItemRecord,
    asset: AssetInfo | None,
    effect: TaxEffect,
) -> JournalEntry:
    """The tax side of the same disposal, as a memo rather than a second ledger.

    This is what makes the book and tax difference visible side by side on the
    ticket. It posts to no real ledger.
    """
    basis_cents = record.tax_basis_cents
    loss = effect.deduction_cents
    gain = effect.gain_cents

    lines: list[JournalLine] = []
    if gain > 0:
        lines.append(JournalLine(account=Account.cash, debit_cents=gain))
        lines.append(JournalLine(account=Account.gain_on_disposal, credit_cents=gain))
    elif loss > 0:
        lines.append(JournalLine(account=Account.loss_on_disposal, debit_cents=loss))
        lines.append(JournalLine(account=Account.fixed_assets, credit_cents=loss))

    difference = record.book_value_cents - basis_cents
    entry = JournalEntry(
        memo=f"Tax treatment of {record.label}",
        basis=Basis.tax_memo,
        lines=lines,
        evidence=_evidence(
            record,
            asset_tag=asset.tag if asset else None,
            tax_basis_cents=basis_cents,
            tax_loss_cents=loss,
            tax_gain_cents=gain,
            tax_effect_cents=effect.tax_effect_cents,
            book_value_cents=record.book_value_cents,
            book_minus_tax_cents=difference,
            rule_ids=list(effect.rule_ids),
            needs_human_review=effect.needs_human_review,
        ),
    )
    return assert_balanced(entry)


class Flag(BaseModel):
    """Something the close should look at. Not a journal entry."""

    model_config = ConfigDict(frozen=True)

    kind: str
    event_id: int
    label: str
    amount_cents: int
    threshold_cents: int
    message: str


FLAG_POSSIBLE_UNRECORDED_ASSET = "possible_unrecorded_asset"


def looks_unrecorded(
    item_class: ItemClass, fmv_mid: int | None, threshold_cents: int
) -> bool:
    """The one test for "valuable, untracked, and on nobody's register".

    The close raises it and the ticket shows it, so the rule lives here once rather than
    being written out twice and drifting.
    """
    return (
        item_class is ItemClass.untracked
        and fmv_mid is not None
        and fmv_mid > threshold_cents
    )


def untracked_flag(record: ItemRecord, settings: EngineSettings) -> Flag | None:
    """Raise a flag when something valuable was thrown out that no register knew about."""
    if not looks_unrecorded(
        record.item_class, record.fmv_mid, settings.capitalization_threshold_cents
    ):
        return None
    value = record.fmv_mid
    assert value is not None
    return Flag(
        kind=FLAG_POSSIBLE_UNRECORDED_ASSET,
        event_id=record.event_id,
        label=record.label,
        amount_cents=value,
        threshold_cents=settings.capitalization_threshold_cents,
        message=(
            f"{record.label} is worth about {money(value)}, above the "
            f"{money(settings.capitalization_threshold_cents)} limit for putting an item on "
            "the register. It was not on the register."
        ),
    )


def reversal(entry: JournalEntry) -> JournalEntry:
    """The entry that undoes another one. Nothing is ever deleted."""
    reversed_entry = JournalEntry(
        memo=f"Reversal of: {entry.memo}",
        basis=entry.basis,
        lines=[
            JournalLine(
                account=line.account,
                debit_cents=line.credit_cents,
                credit_cents=line.debit_cents,
            )
            for line in entry.lines
        ],
        evidence={**entry.evidence, "reverses": entry.memo},
    )
    return assert_balanced(reversed_entry)


def trial_balance(entries: list[JournalEntry]) -> dict[Account, int]:
    """Net debit minus credit per account, across book entries only."""
    totals: dict[Account, int] = {}
    for entry in entries:
        if entry.basis is not Basis.book:
            continue
        for line in entry.lines:
            totals[line.account] = (
                totals.get(line.account, 0) + line.debit_cents - line.credit_cents
            )
    return totals
