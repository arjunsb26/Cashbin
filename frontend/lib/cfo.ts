// The four blocks the CFO reads, until contracts carries them.
//
// Lane P's backend hangs these off `CloseRead`, and the generated types land on
// main shortly. These are the same fields with the same names, every one of them
// optional on the way in, so a close written before the blocks existed draws the
// statement it always drew and each block appears the moment its data does. Swap
// the import for the contract type when it arrives.
//
// PLAN.md 21a item 39.

import type { CloseRead } from "./types";

export type RollforwardRow = {
  asset_id?: number | null;
  tag?: string;
  description?: string;
  opening_cost_cents?: number;
  additions_cents?: number;
  disposals_cost_cents?: number;
  closing_cost_cents?: number;
  opening_accum_cents?: number;
  depreciation_cents?: number;
  disposals_accum_cents?: number;
  closing_accum_cents?: number;
  opening_nbv_cents?: number;
  closing_nbv_cents?: number;
};

export type RollforwardBlock = {
  period_start?: string;
  period_end?: string;
  rows?: RollforwardRow[];
  total?: RollforwardRow;
  /** The backend's own answer to whether the columns foot. */
  ties?: boolean;
};

export type ReconciliationRow = {
  event_id: number;
  asset_id?: number | null;
  tag?: string;
  description?: string;
  book_loss_cents?: number;
  tax_loss_cents?: number;
  difference_cents?: number;
  reason?: string;
  rule_ids?: string[];
};

export type ReconciliationBlock = {
  title?: string;
  rows?: ReconciliationRow[];
  book_loss_cents?: number;
  differences_cents?: number;
  tax_loss_cents?: number;
  ties?: boolean;
};

export type Form4797Row = {
  part?: "II" | "III";
  line?: string;
  description?: string;
  date_acquired?: string;
  date_disposed?: string;
  gross_proceeds_cents?: number;
  cost_cents?: number;
  depreciation_allowed_cents?: number;
  gain_or_loss_cents?: number;
  recapture_note?: string;
  rule_ids?: string[];
};

export type Form4797Block = {
  part_ii_rows?: Form4797Row[];
  part_ii_line_10_cents?: number;
  part_iii_rows?: Form4797Row[];
  part_iii_recapture_cents?: number;
  disclaimer?: string;
};

/** A close as it stands once the four blocks exist. */
export type CloseWithBlocks = CloseRead & {
  memo_md?: string | null;
  rollforward?: RollforwardBlock | null;
  reconciliation?: ReconciliationBlock | null;
  form4797?: Form4797Block | null;
};

export function blocksOf(close: CloseRead | null | undefined): {
  memo: string | null;
  rollforward: RollforwardBlock | null;
  reconciliation: ReconciliationBlock | null;
  form4797: Form4797Block | null;
} {
  const read = (close ?? {}) as CloseWithBlocks;
  return {
    memo: read.memo_md ?? null,
    rollforward: read.rollforward ?? null,
    reconciliation: read.reconciliation ?? null,
    form4797: read.form4797 ?? null,
  };
}

/** What a row put into and took out of the register, on a net book value basis. */
export function rollforwardParts(row: RollforwardRow): {
  opening: number;
  additions: number;
  depreciation: number;
  disposals: number;
  closing: number;
  /** True when opening plus movements really does equal closing. */
  foots: boolean;
} {
  const opening = row.opening_nbv_cents ?? (row.opening_cost_cents ?? 0) - (row.opening_accum_cents ?? 0);
  const additions = row.additions_cents ?? 0;
  const depreciation = row.depreciation_cents ?? 0;
  const disposals = (row.disposals_cost_cents ?? 0) - (row.disposals_accum_cents ?? 0);
  const closing = row.closing_nbv_cents ?? (row.closing_cost_cents ?? 0) - (row.closing_accum_cents ?? 0);
  return {
    opening,
    additions,
    depreciation,
    disposals,
    closing,
    foots: opening + additions - depreciation - disposals === closing,
  };
}

/** True when the M-1 block reconciles: book loss less the differences is the tax loss. */
export function reconciliationFoots(block: ReconciliationBlock | null): boolean {
  if (!block) return true;
  if (typeof block.ties === "boolean") return block.ties;
  return (
    (block.book_loss_cents ?? 0) - (block.differences_cents ?? 0) === (block.tax_loss_cents ?? 0)
  );
}
