"use client";

import { useState } from "react";
import Link from "next/link";
import * as Tabs from "@radix-ui/react-tabs";
import { useJournal } from "@/lib/api";
import { entrySides, formatDate, formatMoney } from "@/lib/format";
import type { JournalBasis, TrialBalanceRow } from "@/lib/types";
import { accountWords } from "@/components/TAccounts";
import { Money } from "@/components/Figure";
import {
  EmptyState,
  ErrorState,
  FinanceFooter,
  PageHeader,
  Select,
  Skeleton,
  cx,
} from "@/components/ui";

export default function BooksPage() {
  const [basis, setBasis] = useState<JournalBasis | "all">("all");
  const journal = useJournal();
  const all = journal.data?.entries ?? [];
  const entries = all.filter((e) => basis === "all" || e.basis === basis);
  const trial = journal.data?.trial_balance ?? [];

  return (
    <div>
      <PageHeader
        title="Books"
        right={
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
        }
      />

      <Tabs.Root defaultValue="journal">
        <Tabs.List className="flex gap-4 border-b border-rule" aria-label="Books views">
          <TabTrigger value="journal">Journal</TabTrigger>
          <TabTrigger value="trial">Trial balance</TabTrigger>
        </Tabs.List>

        <Tabs.Content value="journal" className="pt-4">
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
          {entries.length > 0 ? (
            <div className="overflow-x-auto">
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
                      <tr key={line.id} className="h-row border-b border-rule hover:bg-bar">
                        <td className="whitespace-nowrap text-ink-soft">
                          {i === 0 ? formatDate(entry.posted_at) : ""}
                        </td>
                        <td>{accountWords(line)}</td>
                        <td className="text-ink-soft">{i === 0 ? entry.memo : ""}</td>
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
        </Tabs.Content>

        <Tabs.Content value="trial" className="pt-4">
          {journal.isPending ? <TableSkeleton /> : null}
          {journal.isError ? (
            <ErrorState
              title="The trial balance did not load. The backend is not answering."
              onRetry={() => journal.refetch()}
            />
          ) : null}
          {journal.data && trial.length === 0 ? (
            <EmptyState title="Nothing posted yet, so the trial balance is empty." />
          ) : null}
          {trial.length > 0 ? (
            <TrialBalance rows={trial} balanced={journal.data?.balanced ?? true} />
          ) : null}
        </Tabs.Content>
      </Tabs.Root>

      <FinanceFooter />
    </div>
  );
}

function TrialBalance({ rows, balanced }: { rows: TrialBalanceRow[]; balanced: boolean }) {
  const debits = rows.reduce((sum, r) => sum + (r.debit_cents ?? 0), 0);
  const credits = rows.reduce((sum, r) => sum + (r.credit_cents ?? 0), 0);
  return (
    <div className="overflow-x-auto">
      <table className="ledger green-bar w-full min-w-[420px] max-w-[720px] border-collapse text-body">
        <thead>
          <tr className="border-b border-rule text-caption text-ink-soft">
            <th className="py-1 font-normal">Account</th>
            <th className="py-1 text-right font-normal">Debit ($)</th>
            <th className="py-1 text-right font-normal">Credit ($)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.account} className="h-row border-b border-rule hover:bg-bar">
              <td>{row.account_name || row.account}</td>
              <td className="text-right">
                {(row.debit_cents ?? 0) > 0 ? formatMoney(row.debit_cents ?? 0) : ""}
              </td>
              <td className="text-right">
                {(row.credit_cents ?? 0) > 0 ? formatMoney(row.credit_cents ?? 0) : ""}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="h-row border-t border-ink">
            <td>Totals</td>
            <td className="text-right">{formatMoney(debits, { symbol: true })}</td>
            <td className="text-right">{formatMoney(credits, { symbol: true })}</td>
          </tr>
        </tfoot>
      </table>
      {!balanced ? (
        <p className="border-l-2 border-red-ink pl-3 pt-3 text-body">
          The two columns do not agree. The close names the entries that caused it.
        </p>
      ) : null}
    </div>
  );
}

function TabTrigger({ value, children }: { value: string; children: string }) {
  return (
    <Tabs.Trigger
      value={value}
      className={cx(
        "-mb-px border-b-2 border-transparent px-1 pb-2 text-section text-ink-soft",
        "data-[state=active]:border-b-ink data-[state=active]:text-ink",
      )}
    >
      {children}
    </Tabs.Trigger>
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
