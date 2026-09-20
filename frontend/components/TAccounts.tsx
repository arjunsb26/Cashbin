"use client";

import { useState } from "react";
import type { JournalEntryRead } from "@/lib/types";
import { entrySides, formatMoney } from "@/lib/format";
import { Button, EmptyState, SectionTitle } from "./ui";

/**
 * Book on the left, tax on the right, with the difference said in one sentence.
 * The toggle swaps to the plain journal table for people who prefer it.
 */
export function TAccounts({
  entries,
  difference,
  names,
}: {
  entries: JournalEntryRead[];
  difference: string;
  /** Account code to account name, where the read that carries them was made. */
  names?: Map<string, string>;
}) {
  const [asTable, setAsTable] = useState(false);
  const book = entries.filter((e) => e.basis === "book");
  const tax = entries.filter((e) => e.basis === "tax_memo");

  if (entries.length === 0) {
    return <EmptyState title="No entry yet. One posts as soon as the label is final." />;
  }

  return (
    <section className="flex flex-col gap-3">
      <SectionTitle
        right={
          <Button onClick={() => setAsTable((v) => !v)}>
            {asTable ? "Show T-accounts" : "Show the journal table"}
          </Button>
        }
      >
        Book and tax
      </SectionTitle>

      {asTable ? (
        <JournalTable entries={entries} names={names} />
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <TColumn title="Book" entries={book} names={names} />
          <TColumn title="Tax" entries={tax} names={names} />
        </div>
      )}

      <p className="text-body text-ink-soft">{difference}</p>
    </section>
  );
}

/** The account name where the ledger gives one, the code where it does not. */
export function accountWords(
  line: { account: string; account_name?: string | null },
  names?: Map<string, string>,
): string {
  return line.account_name ?? names?.get(line.account) ?? line.account;
}

function TColumn({
  title,
  entries,
  names,
}: {
  title: string;
  entries: JournalEntryRead[];
  names?: Map<string, string>;
}) {
  if (entries.length === 0) {
    return (
      <div>
        <h3 className="text-section">{title}</h3>
        <p className="pt-2 text-body text-ink-soft">No entry on this side.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-section">{title}</h3>
      {entries.map((entry) => {
        const lines = entry.lines ?? [];
        const sides = entrySides(
          lines.map((l) => ({ debit_cents: l.debit_cents ?? 0, credit_cents: l.credit_cents ?? 0 })),
        );
        return (
          <div key={entry.id}>
            <p className="border-b border-ink pb-1 text-body">{entry.memo}</p>
            {lines.length === 0 ? (
              <p className="pt-2 text-body text-ink-soft">
                This memo moves nothing, so it has no lines.
              </p>
            ) : (
            <div className="grid grid-cols-2">
              <ul className="m-0 list-none border-r border-ink p-0 pr-3 pt-2">
                {lines
                  .filter((_, i) => sides[i] === "debit")
                  .map((line) => (
                    <li key={line.id} className="flex justify-between gap-3 py-1 text-body">
                      <span className="min-w-0 truncate">{accountWords(line, names)}</span>
                      <span>{formatMoney(line.debit_cents ?? 0)}</span>
                    </li>
                  ))}
              </ul>
              <ul className="m-0 list-none p-0 pl-3 pt-2">
                {lines
                  .filter((_, i) => sides[i] === "credit")
                  .map((line) => (
                    <li key={line.id} className="flex justify-between gap-3 py-1 text-body">
                      <span className="min-w-0 truncate">{accountWords(line, names)}</span>
                      <span>{formatMoney(line.credit_cents ?? 0)}</span>
                    </li>
                  ))}
              </ul>
            </div>
            )}
            {lines.length > 0 ? (
              <p className="pt-1 text-caption text-ink-soft">Debits left, credits right.</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function JournalTable({
  entries,
  names,
}: {
  entries: JournalEntryRead[];
  names?: Map<string, string>;
}) {
  return (
    <table className="ledger green-bar w-full border-collapse text-body">
      <thead>
        <tr className="border-b border-rule text-caption text-ink-soft">
          <th className="py-1 font-normal">Account</th>
          <th className="py-1 font-normal">Memo</th>
          <th className="py-1 text-right font-normal">Debit ($)</th>
          <th className="py-1 text-right font-normal">Credit ($)</th>
        </tr>
      </thead>
      <tbody>
        {entries.flatMap((entry) => {
          const lines = entry.lines ?? [];
          const sides = entrySides(
            lines.map((l) => ({
              debit_cents: l.debit_cents ?? 0,
              credit_cents: l.credit_cents ?? 0,
            })),
          );
          return lines.map((line, i) => (
            <tr key={line.id} className="h-row border-b border-rule">
              <td>{accountWords(line, names)}</td>
              <td className="text-ink-soft">{entry.memo}</td>
              <td className="text-right">
                {sides[i] === "debit" ? formatMoney(line.debit_cents ?? 0) : ""}
              </td>
              <td className="text-right">
                {sides[i] === "credit" ? formatMoney(line.credit_cents ?? 0) : ""}
              </td>
            </tr>
          ));
        })}
      </tbody>
    </table>
  );
}
