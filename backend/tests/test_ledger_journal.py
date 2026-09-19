from __future__ import annotations

from datetime import date

import pytest

from app.engine import tax
from app.engine.records import (
    AssetInfo,
    EngineSettings,
    EstimateSource,
    ItemClass,
    ItemRecord,
    Option,
    TaxMethod,
)
from app.ledger.journal import (
    Account,
    Basis,
    JournalEntry,
    JournalLine,
    Unbalanced,
    assert_balanced,
    fixed_asset_disposal,
    inventory_toss,
    reversal,
    tax_memo,
    trial_balance,
    untracked_flag,
)
from tests.test_engine_cases import KEYBOARD_ASSET, keyboard_record

EVENT_DATE = date(2026, 9, 19)
SETTINGS = EngineSettings()


def inventory_record(cost_basis_cents: int | None = 66) -> ItemRecord:
    return ItemRecord(
        event_id=2,
        label="bagel",
        item_class=ItemClass.inventory,
        mass_g=95.0,
        event_date=EVENT_DATE,
        material_mix={"food_waste": 1.0},
        cost_basis_cents=cost_basis_cents,
    )


def asset_record(book_value_cents: int) -> ItemRecord:
    return ItemRecord(
        event_id=1,
        label="keyboard",
        item_class=ItemClass.fixed_asset,
        mass_g=685.0,
        event_date=EVENT_DATE,
        material_mix={"electronic_peripherals": 1.0},
        book_value_cents=book_value_cents,
        asset_id=2,
    )


# --- balance -----------------------------------------------------------------


def test_an_unbalanced_entry_raises_with_both_totals() -> None:
    entry = JournalEntry(
        memo="Broken entry",
        lines=[
            JournalLine(account=Account.inventory, debit_cents=500),
            JournalLine(account=Account.cash, credit_cents=400),
        ],
    )
    with pytest.raises(Unbalanced) as caught:
        assert_balanced(entry)
    assert "5.00" in str(caught.value)
    assert "4.00" in str(caught.value)


# --- inventory ---------------------------------------------------------------


def test_inventory_toss_balances_and_hits_the_right_accounts() -> None:
    entry = inventory_toss(inventory_record())
    assert entry is not None
    assert_balanced(entry)
    assert entry.basis is Basis.book
    accounts = {line.account: line for line in entry.lines}
    assert accounts[Account.waste_and_shrink].debit_cents == 66
    assert accounts[Account.inventory].credit_cents == 66
    assert entry.evidence["event_id"] == 2


def test_inventory_toss_posts_nothing_when_the_cost_is_not_known() -> None:
    assert inventory_toss(inventory_record(None)) is None
    assert inventory_toss(inventory_record(0)) is None


# --- fixed asset disposal ----------------------------------------------------


def test_disposal_with_no_proceeds_takes_a_loss_and_balances() -> None:
    entry = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=0)
    assert_balanced(entry)
    lines = {line.account: line for line in entry.lines}
    assert lines[Account.accumulated_depreciation].debit_cents == 6000
    assert lines[Account.loss_on_disposal].debit_cents == 6000
    assert lines[Account.fixed_assets].credit_cents == 12000
    assert Account.gain_on_disposal not in lines


def test_disposal_above_book_value_records_a_gain_and_balances() -> None:
    entry = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=9000)
    assert_balanced(entry)
    lines = {line.account: line for line in entry.lines}
    assert lines[Account.cash].debit_cents == 9000
    assert lines[Account.gain_on_disposal].credit_cents == 3000
    assert Account.loss_on_disposal not in lines


def test_disposal_exactly_at_book_value_has_neither_gain_nor_loss() -> None:
    entry = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=6000)
    assert_balanced(entry)
    accounts = {line.account for line in entry.lines}
    assert Account.gain_on_disposal not in accounts
    assert Account.loss_on_disposal not in accounts


def test_disposal_of_a_fully_depreciated_asset_balances() -> None:
    entry = fixed_asset_disposal(asset_record(0), KEYBOARD_ASSET, proceeds_cents=0)
    assert_balanced(entry)
    assert entry.total_debits_cents == 12000


# --- tax memo ----------------------------------------------------------------


def test_the_tax_memo_shows_the_gap_between_book_and_tax() -> None:
    record = keyboard_record()
    effect = tax.tax_effect_for(Option.trash, record, SETTINGS, KEYBOARD_ASSET)
    assert effect is not None
    entry = tax_memo(record, KEYBOARD_ASSET, effect)
    assert_balanced(entry)
    assert entry.basis is Basis.tax_memo
    assert entry.evidence["tax_basis_cents"] == 0
    assert entry.evidence["book_value_cents"] == 6000
    assert entry.evidence["book_minus_tax_cents"] == 6000
    assert "BONUS_100" in entry.evidence["rule_ids"]


def test_a_tax_memo_with_a_deduction_balances() -> None:
    record = asset_record(6000)
    record = record.model_copy(update={"tax_basis_cents": 6000})
    effect = tax.tax_effect_for(Option.trash, record, SETTINGS)
    assert effect is not None
    entry = tax_memo(record, KEYBOARD_ASSET, effect)
    assert_balanced(entry)
    assert entry.total_debits_cents == 6000


def test_a_tax_memo_on_a_sale_at_a_gain_balances() -> None:
    record = asset_record(6000).model_copy(
        update={
            "tax_basis_cents": 1000,
            "fmv_mid": 5000,
            "fmv_source": EstimateSource.model_estimate,
        }
    )
    effect = tax.tax_effect_for(Option.resell, record, SETTINGS)
    assert effect is not None
    entry = tax_memo(record, KEYBOARD_ASSET, effect)
    assert_balanced(entry)
    assert entry.evidence["tax_gain_cents"] == 4000


# --- flags -------------------------------------------------------------------


def test_a_valuable_untracked_item_raises_a_flag() -> None:
    record = ItemRecord(
        event_id=7,
        label="laptop",
        item_class=ItemClass.untracked,
        mass_g=1400.0,
        event_date=EVENT_DATE,
        fmv_mid=90000,
        fmv_source=EstimateSource.model_estimate,
    )
    flag = untracked_flag(record, SETTINGS)
    assert flag is not None
    assert flag.kind == "possible_unrecorded_asset"
    assert "900.00" in flag.message


def test_a_cheap_untracked_item_raises_nothing() -> None:
    record = ItemRecord(
        event_id=8,
        label="charger",
        item_class=ItemClass.untracked,
        mass_g=31.0,
        event_date=EVENT_DATE,
        fmv_mid=500,
        fmv_source=EstimateSource.model_estimate,
    )
    assert untracked_flag(record, SETTINGS) is None


def test_an_item_on_the_register_is_not_an_unrecorded_asset() -> None:
    record = asset_record(6000).model_copy(
        update={"fmv_mid": 90000, "fmv_source": EstimateSource.model_estimate}
    )
    assert untracked_flag(record, SETTINGS) is None


# --- void --------------------------------------------------------------------


def test_a_void_reverses_the_entry_exactly() -> None:
    entry = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=9000)
    undo = reversal(entry)
    assert_balanced(undo)
    assert undo.total_debits_cents == entry.total_credits_cents
    assert undo.total_credits_cents == entry.total_debits_cents
    for before, after in zip(entry.lines, undo.lines, strict=True):
        assert before.account is after.account
        assert before.debit_cents == after.credit_cents
        assert before.credit_cents == after.debit_cents
    assert undo.evidence["reverses"] == entry.memo


def test_an_entry_and_its_reversal_leave_the_trial_balance_at_zero() -> None:
    entry = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=0)
    totals = trial_balance([entry, reversal(entry)])
    assert all(value == 0 for value in totals.values())


def test_the_trial_balance_of_book_entries_sums_to_zero() -> None:
    toss = inventory_toss(inventory_record())
    disposal = fixed_asset_disposal(asset_record(6000), KEYBOARD_ASSET, proceeds_cents=9000)
    assert toss is not None
    totals = trial_balance([toss, disposal])
    assert sum(totals.values()) == 0


def test_a_tax_memo_never_reaches_the_trial_balance() -> None:
    record = asset_record(6000).model_copy(update={"tax_basis_cents": 6000})
    effect = tax.tax_effect_for(Option.trash, record, SETTINGS)
    assert effect is not None
    assert trial_balance([tax_memo(record, KEYBOARD_ASSET, effect)]) == {}


def test_every_builder_balances_for_a_bare_asset() -> None:
    bare = AssetInfo(
        id=99,
        tag="BB-0099",
        description="Bare asset",
        cost_cents=5000,
        in_service_date=date(2026, 1, 1),
        book_life_months=12,
        tax_method=TaxMethod.straight_line,
    )
    record = asset_record(2000).model_copy(update={"tax_basis_cents": 2000})
    for entry in (
        fixed_asset_disposal(record, bare, 0),
        fixed_asset_disposal(record, bare, 500),
        fixed_asset_disposal(record, bare, 5000),
    ):
        assert_balanced(entry)
        assert_balanced(reversal(entry))
