"use client";

import type { RoundRead, SummaryResponse } from "@/lib/types";
import { useWaiting } from "@/lib/api";
import { formatCount, formatMoney, formatPercent, massParts } from "@/lib/format";
import { waitingSentence } from "@/lib/copy";
import { cx } from "./ui";

/**
 * The foot of the tape.
 *
 * A ledger column carries its total at the bottom, so the printed tape does too:
 * what the round kept out of the ground, what following the best answer would
 * have been worth, and how often the bin got it right without asking. It stands
 * where the tape runs out, so the column is a column of numbers to its end.
 */
export function RoundTotals({
  summary,
  round,
}: {
  summary: SummaryResponse | undefined;
  round: RoundRead | null;
}) {
  const waiting = useWaiting();
  if (!summary) return null;
  const mass = massParts((summary.kg_diverted ?? 0) * 1000);
  const accuracy = round?.first_try_accuracy ?? null;

  return (
    <section aria-label="Round total" className="mt-6 border-t-2 border-ink pt-3">
      <h3 className="text-caption text-ink-soft">Round total</h3>
      <dl className="m-0 pt-2">
        <Line label="Projected waste diverted" value={`${mass.value} ${mass.unit}`} />
        <Line
          label="Expected savings"
          value={formatMoney(summary.saved_if_followed_cents ?? 0, { symbol: true })}
        />
        <Line
          label="Tosses"
          value={formatCount(round?.n_events ?? summary.events ?? 0)}
          last={accuracy === null}
        />
      </dl>

      {accuracy === null ? null : (
        <div className="pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-body text-ink-soft">Right first try</span>
            <span className="text-body">{formatPercent(accuracy)}</span>
          </div>
          <AccuracyBar fraction={accuracy} />
          {/* The count of things waiting on a person comes from the queue, the
              same place the rail reads, so the tape and the rail cannot differ. */}
          <p className="pt-1 text-caption text-ink-soft">{waitingSentence(waiting)}</p>
        </div>
      )}
    </section>
  );
}

function Line({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <div className={cx("flex items-baseline justify-between py-1", !last && "border-b border-rule")}>
      <dt className="text-body text-ink-soft">{label}</dt>
      <dd className="m-0 text-body">{value}</dd>
    </div>
  );
}

/**
 * Drawn by hand out of two blocks, because a bar this small is two blocks and a
 * chart library would put its own look on it.
 */
function AccuracyBar({ fraction }: { fraction: number }) {
  const width = `${Math.round(Math.min(Math.max(fraction, 0), 1) * 100)}%`;
  return (
    <div className="mt-2 h-2 w-full bg-bar" aria-hidden="true">
      <div className="h-2 bg-ink" style={{ width }} />
    </div>
  );
}

