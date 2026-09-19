"""The database side of the ledger: post an entry, read it back, void an event.

`ledger/journal.py` stays pure. This module is the only place where a journal
entry meets the ORM. It writes the pure `JournalEntry` into `journal_entry` and
`journal_line`, and reads rows back as the wire types in `schemas.py`, so the
API handler does nothing but call these functions.

An entry is checked with `assert_balanced` before a single row is written, so an
unbalanced entry never reaches the database.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.ledger.journal import Account, Basis, JournalEntry, assert_balanced, reversal
from app.schemas import JournalEntryRead, JournalLineRead, TrialBalanceRow


def account_code(account: Account | str) -> str:
    """The four digit code the database stores, from the chart of accounts name."""
    text = account.value if isinstance(account, Account) else str(account)
    return text.split(" ", 1)[0]


def account_name(code: str) -> str:
    """The name a person reads beside the code, from the one chart of accounts."""
    return models.CHART_OF_ACCOUNTS.get(code, "")


def _basis_value(basis: Basis | models.JournalBasis | str) -> models.JournalBasis:
    text = basis.value if isinstance(basis, Basis | models.JournalBasis) else str(basis)
    return models.JournalBasis(text)


def post_entry(
    session: Session,
    entry: JournalEntry,
    event_id: int | None = None,
    close_id: int | None = None,
) -> models.JournalEntry:
    """Write one balanced entry and its lines. Returns the row, already flushed.

    The caller commits. `evidence_json` carries the audit trail PLAN.md section
    11 asks for: the event, the media, the mass, the identification and the rule
    ids, whatever the builder put on the entry.
    """
    assert_balanced(entry)
    evidence: dict[str, Any] = dict(entry.evidence)
    if event_id is not None:
        evidence.setdefault("event_id", event_id)

    row = models.JournalEntry(
        event_id=event_id,
        close_id=close_id,
        memo=entry.memo,
        basis=_basis_value(entry.basis),
        evidence_json=json.dumps(evidence),
    )
    session.add(row)
    session.flush()

    for line in entry.lines:
        session.add(
            models.JournalLine(
                entry_id=row.id,
                account=account_code(line.account),
                debit_cents=line.debit_cents,
                credit_cents=line.credit_cents,
            )
        )
    session.flush()
    return row


def _read_entry(row: models.JournalEntry, lines: list[models.JournalLine]) -> JournalEntryRead:
    evidence: dict[str, Any] = {}
    if row.evidence_json:
        loaded = json.loads(row.evidence_json)
        if isinstance(loaded, dict):
            evidence = loaded
    return JournalEntryRead(
        id=row.id,
        event_id=row.event_id,
        close_id=row.close_id,
        posted_at=row.posted_at,
        memo=row.memo,
        basis=row.basis,
        evidence=evidence,
        lines=[
            JournalLineRead(
                id=line.id,
                entry_id=line.entry_id,
                account=line.account,
                account_name=account_name(line.account),
                debit_cents=line.debit_cents,
                credit_cents=line.credit_cents,
            )
            for line in lines
        ],
    )


def list_entries(
    session: Session,
    basis: models.JournalBasis | str | None = None,
    event_id: int | None = None,
) -> list[JournalEntryRead]:
    """Every entry, oldest first, with its lines and the account names filled in."""
    query = select(models.JournalEntry).order_by(
        models.JournalEntry.posted_at, models.JournalEntry.id
    )
    if basis is not None:
        query = query.where(models.JournalEntry.basis == _basis_value(basis))
    if event_id is not None:
        query = query.where(models.JournalEntry.event_id == event_id)
    rows = list(session.scalars(query))
    if not rows:
        return []

    ids = [row.id for row in rows]
    line_query = (
        select(models.JournalLine)
        .where(models.JournalLine.entry_id.in_(ids))
        .order_by(models.JournalLine.id)
    )
    by_entry: dict[int, list[models.JournalLine]] = {entry_id: [] for entry_id in ids}
    for line in session.scalars(line_query):
        by_entry[line.entry_id].append(line)

    return [_read_entry(row, by_entry[row.id]) for row in rows]


def trial_balance(
    session: Session,
    basis: models.JournalBasis | str | None = None,
) -> list[TrialBalanceRow]:
    """Debits and credits per account, in account code order.

    Totals are gross, not netted, because a trial balance is the check that the
    two columns agree. The tax memo basis is a memo, so it is only included when
    it is asked for by name.
    """
    wanted = _basis_value(basis) if basis is not None else models.JournalBasis.book
    query = (
        select(
            models.JournalLine.account,
            models.JournalLine.debit_cents,
            models.JournalLine.credit_cents,
        )
        .join(models.JournalEntry, models.JournalEntry.id == models.JournalLine.entry_id)
        .where(models.JournalEntry.basis == wanted)
    )
    debit_totals: dict[str, int] = {}
    credit_totals: dict[str, int] = {}
    for account, debit, credit in session.execute(query):
        debit_totals[account] = debit_totals.get(account, 0) + debit
        credit_totals[account] = credit_totals.get(account, 0) + credit

    return [
        TrialBalanceRow(
            account=account,
            account_name=account_name(account),
            debit_cents=debit_totals.get(account, 0),
            credit_cents=credit_totals.get(account, 0),
        )
        for account in sorted(set(debit_totals) | set(credit_totals))
    ]


def is_balanced(rows: list[TrialBalanceRow]) -> bool:
    """True when the two columns of the trial balance agree."""
    return sum(row.debit_cents for row in rows) == sum(row.credit_cents for row in rows)


def _to_pure(row: models.JournalEntry, lines: list[models.JournalLine]) -> JournalEntry:
    """Turn a stored entry back into the pure type, so `reversal` can work on it."""
    by_code = {account_code(account): account for account in Account}
    evidence: dict[str, Any] = {}
    if row.evidence_json:
        loaded = json.loads(row.evidence_json)
        if isinstance(loaded, dict):
            evidence = loaded
    from app.ledger.journal import JournalLine as PureLine

    return JournalEntry(
        memo=row.memo,
        basis=Basis(row.basis.value),
        lines=[
            PureLine(
                account=by_code[line.account],
                debit_cents=line.debit_cents,
                credit_cents=line.credit_cents,
            )
            for line in lines
        ],
        evidence=evidence,
    )


def void_event(session: Session, event_id: int) -> list[int]:
    """Post a reversing entry for every entry of this event. Nothing is deleted.

    An entry that is itself a reversal is left alone, so voiding twice does not
    undo the void.
    """
    query = (
        select(models.JournalEntry)
        .where(models.JournalEntry.event_id == event_id)
        .order_by(models.JournalEntry.id)
    )
    rows = list(session.scalars(query))
    if not rows:
        return []

    prefix = "Reversal of: "
    already_reversed = {
        row.memo.removeprefix(prefix) for row in rows if row.memo.startswith(prefix)
    }

    new_ids: list[int] = []
    for row in rows:
        if row.memo.startswith(prefix) or row.memo in already_reversed:
            continue
        lines = list(
            session.scalars(
                select(models.JournalLine)
                .where(models.JournalLine.entry_id == row.id)
                .order_by(models.JournalLine.id)
            )
        )
        posted = post_entry(
            session,
            reversal(_to_pure(row, lines)),
            event_id=event_id,
            close_id=row.close_id,
        )
        new_ids.append(posted.id)
    return new_ids
