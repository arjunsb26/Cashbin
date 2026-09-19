"use client";

import { useState } from "react";
import type { JournalEntry } from "@/lib/types";
import { entrySides, formatMoney } from "@/lib/format";
import { Button, EmptyState, SectionTitle } from "./ui";

/**
 * Book on the left, tax on the right, with the difference said in one sentence.
 * The toggle swaps to the plain journal table for people who prefer it.
 */
export function TAccounts({
  entries,
  difference,
}: {
  entries: JournalEntry[];
  difference: string;
}) {
  const [asTable, setAsTable] = useState(false);
  const book = entries.filter((e) => e.basis === "book");
  const tax = entries.filter((e) => e.basis === "tax_memo");

  if (entries.length === 0) {
    return (
      <EmptyState title="No entry yet. One posts as soon as the label is final." />
    );
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
        <JournalTable entries={entries} />
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <TColumn title="Book" entries={book} />
          <TColumn title="Tax" entries={tax} />
        </div>
      )}

      <p className="text-body text-ink-soft">{difference}</p>
    </section>
  );
}

function TColumn({ title, entries }: { title: string; entries: JournalEntry[] }) {
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
        const sides = entrySides(entry.lines);
        return (
        <div key={entry.id}>
          <p className="border-b border-ink pb-1 text-body">{entry.memo}</p>
          <div className="grid grid-cols-2">
            <ul className="m-0 list-none border-r border-ink p-0 pr-3 pt-2">
              {entry.lines
                .filter((_, i) => sides[i] === "debit")
                .map((line) => (
                  <li key={line.account} className="flex justify-between gap-3 py-1 text-body">
                    <span className="min-w-0 truncate">{line.account}</span>
                    <span>{formatMoney(line.debit_cents)}</span>
                  </li>
                ))}
            </ul>
            <ul className="m-0 list-none p-0 pl-3 pt-2">
              {entry.lines
                .filter((_, i) => sides[i] === "credit")
                .map((line) => (
                  <li key={line.account} className="flex justify-between gap-3 py-1 text-body">
                    <span className="min-w-0 truncate">{line.account}</span>
                    <span>{formatMoney(line.credit_cents)}</span>
                  </li>
                ))}
            </ul>
          </div>
          <p className="pt-1 text-caption text-ink-soft">Debits left, credits right.</p>
        </div>
        );
      })}
    </div>
  );
}

export function JournalTable({ entries }: { entries: JournalEntry[] }) {
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
          const sides = entrySides(entry.lines);
          return entry.lines.map((line, i) => (
            <tr key={`${entry.id}-${line.account}`} className="h-row border-b border-rule">
              <td>{line.account}</td>
              <td className="text-ink-soft">{entry.memo}</td>
              <td className="text-right">
                {sides[i] === "debit" ? formatMoney(line.debit_cents) : ""}
              </td>
              <td className="text-right">
                {sides[i] === "credit" ? formatMoney(line.credit_cents) : ""}
              </td>
            </tr>
          ));
        })}
      </tbody>
    </table>
  );
}
