"use client";

import { useJournal } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { TrialBalanceRow } from "@/lib/types";
import { EmptyState, ErrorState, Skeleton } from "./ui";

/** Every account with what it holds, and the proof that the two columns agree. */
export function TrialBalanceView() {
  const journal = useJournal();
  const trial = journal.data?.trial_balance ?? [];

  return (
    <div>
      {journal.isPending ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-row w-full" />
          ))}
        </div>
      ) : null}
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
    </div>
  );
}

function TrialBalance({
  rows,
  balanced,
}: {
  rows: TrialBalanceRow[];
  balanced: boolean;
}) {
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
            <tr
              key={row.account}
              className="h-row border-b border-rule hover:bg-bar"
            >
              <td>{row.account_name || row.account}</td>
              <td className="text-right">
                {(row.debit_cents ?? 0) > 0
                  ? formatMoney(row.debit_cents ?? 0)
                  : ""}
              </td>
              <td className="text-right">
                {(row.credit_cents ?? 0) > 0
                  ? formatMoney(row.credit_cents ?? 0)
                  : ""}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="h-row border-t border-ink">
            <td>Totals</td>
            <td className="text-right">
              {formatMoney(debits, { symbol: true })}
            </td>
            <td className="text-right">
              {formatMoney(credits, { symbol: true })}
            </td>
          </tr>
        </tfoot>
      </table>
      {!balanced ? (
        <p className="border-l-2 border-red-ink pl-3 pt-3 text-body">
          The two columns do not agree. The close names the entries that caused
          it.
        </p>
      ) : null}
    </div>
  );
}
