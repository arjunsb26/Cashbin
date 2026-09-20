"use client";

import { useState } from "react";
import Link from "next/link";
import { useJournal } from "@/lib/api";
import { entrySides, formatDate } from "@/lib/format";
import type { JournalBasis } from "@/lib/types";
import { accountWords } from "./TAccounts";
import { Money } from "./Figure";
import { EmptyState, ErrorState, Select, Skeleton, cx } from "./ui";

/** The journal as a ruled tape of entries, book and tax side by side. */
export function Journal() {
  const [basis, setBasis] = useState<JournalBasis | "all">("all");
  const journal = useJournal();
  const all = journal.data?.entries ?? [];
  const entries = all.filter((e) => basis === "all" || e.basis === basis);

  return (
    <div>
      <div className="flex justify-end pb-3">
        <label className="flex items-center gap-2 text-caption text-ink-soft">
          View
          <Select
            value={basis}
            onChange={(e) => setBasis(e.target.value as JournalBasis | "all")}
            aria-label="Which set of entries to show"
          >
            <option value="all">Book and tax</option>
            <option value="book">Book only</option>
            <option value="tax_memo">Tax memo only</option>
          </Select>
        </label>
      </div>

      {journal.isPending ? <TableSkeleton /> : null}
      {journal.isError ? (
        <ErrorState
          title="The journal did not load. The backend is not answering."
          onRetry={() => journal.refetch()}
        />
      ) : null}
      {journal.data && entries.length === 0 ? (
        <EmptyState title="No entries in this view yet. They post as tickets are finalised." />
      ) : null}
      {/* A phone gets one card per entry with every column in it, because a
          seven column table at 390 px either scrolls sideways or drops columns,
          and both hide half the entry. The table starts at the md breakpoint. */}
      {entries.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-3 p-0 md:hidden">
          {entries.map((entry) => {
            const lines = entry.lines ?? [];
            const sides = entrySides(
              lines.map((l) => ({
                debit_cents: l.debit_cents ?? 0,
                credit_cents: l.credit_cents ?? 0,
              })),
            );
            return (
              <li key={entry.id} className="border border-rule bg-surface p-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-caption text-ink-soft">
                    {formatDate(entry.posted_at)}, {entry.basis === "book" ? "book" : "tax memo"}
                  </span>
                  {entry.event_id ? (
                    <Link
                      className="text-caption underline underline-offset-2"
                      href={`/events/${entry.event_id}`}
                    >
                      Ticket {entry.event_id}
                    </Link>
                  ) : null}
                </div>
                {entry.memo ? <p className="pt-1 text-body">{entry.memo}</p> : null}
                <ul className="m-0 list-none p-0 pt-2">
                  {lines.map((line, i) => (
                    <li
                      key={line.id}
                      className="flex items-baseline justify-between gap-3 border-t border-rule py-1.5"
                    >
                      <span className={cx("text-body", sides[i] === "credit" && "pl-4")}>
                        {accountWords(line)}
                      </span>
                      <span className="whitespace-nowrap text-body">
                        <span className="text-caption text-ink-soft">
                          {sides[i] === "debit" ? "Debit " : "Credit "}
                        </span>
                        <Money
                          cents={sides[i] === "debit" ? (line.debit_cents ?? 0) : (line.credit_cents ?? 0)}
                          eventId={entry.event_id}
                          focus={sides[i] === "debit" ? "debit" : "credit"}
                        />
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      ) : null}
      {entries.length > 0 ? (
        <div className="hidden overflow-x-auto md:block">
          <table className="ledger green-bar w-full min-w-[840px] border-collapse text-body">
            <thead>
              <tr className="border-b border-rule text-caption text-ink-soft">
                <th className="py-1 font-normal">Posted</th>
                <th className="py-1 font-normal">Account</th>
                <th className="py-1 font-normal">Memo</th>
                <th className="py-1 font-normal">Basis</th>
                <th className="py-1 text-right font-normal">Debit ($)</th>
                <th className="py-1 text-right font-normal">Credit ($)</th>
                <th className="py-1 text-right font-normal">Ticket</th>
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
                  <tr
                    key={line.id}
                    className="h-row border-b border-rule hover:bg-bar"
                  >
                    <td className="whitespace-nowrap text-ink-soft">
                      {i === 0 ? formatDate(entry.posted_at) : ""}
                    </td>
                    <td>{accountWords(line)}</td>
                    <td className="text-ink-soft">
                      {i === 0 ? entry.memo : ""}
                    </td>
                    <td className="whitespace-nowrap text-ink-soft">
                      {entry.basis === "book" ? "Book" : "Tax memo"}
                    </td>
                    <td className="text-right">
                      {sides[i] === "debit" ? (
                        <Money
                          cents={line.debit_cents ?? 0}
                          eventId={entry.event_id}
                          focus="debit"
                        />
                      ) : null}
                    </td>
                    <td className="text-right">
                      {sides[i] === "credit" ? (
                        <Money
                          cents={line.credit_cents ?? 0}
                          eventId={entry.event_id}
                          focus="credit"
                        />
                      ) : null}
                    </td>
                    <td className="text-right">
                      {entry.event_id && i === 0 ? (
                        <Link
                          className="underline underline-offset-2"
                          href={`/events/${entry.event_id}`}
                        >
                          {entry.event_id}
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                ));
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-row w-full" />
      ))}
    </div>
  );
}
