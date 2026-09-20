"use client";

import type { VisionCandidate } from "@/lib/types";
import { formatProbability } from "@/lib/format";

/** One set of candidate probabilities. Two of these sit side by side in the drawer. */
export function ProbabilityBars({
  title,
  candidates,
  note,
}: {
  title: string;
  candidates: VisionCandidate[];
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-caption text-ink-soft">{title}</h4>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {candidates.map((c) => (
          <li key={c.label} className="grid grid-cols-[88px_1fr_36px] items-center gap-2">
            <span className="truncate text-caption">{c.label}</span>
            <span className="h-2 bg-bar">
              <span
                className="block h-2 bg-ink"
                style={{ width: `${Math.round(c.p * 100)}%` }}
                aria-hidden="true"
              />
            </span>
            <span className="text-right text-caption text-ink-soft">
              {formatProbability(c.p)}
            </span>
          </li>
        ))}
      </ul>
      {note ? <p className="text-caption text-ink-soft">{note}</p> : null}
    </div>
  );
}
