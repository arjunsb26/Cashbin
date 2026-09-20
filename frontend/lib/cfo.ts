// The arithmetic behind the four blocks a CFO reads.
//
// The block shapes used to be restated here, because the backend was being
// written as the screen was. They hang off `CloseRead` in the contract now, so
// `blocksOf` reads them straight off the close with no cast and a schema change
// reaches this screen as a type error. What is left here is the checking: whether
// a rollforward row foots and whether the M-1 block reconciles.
//
// PLAN.md 21a item 39.

import type {
  CloseRead,
  Form4797Block,
  ReconciliationBlock,
  RollforwardBlock,
  RollforwardRow,
} from "./types";

export function blocksOf(close: CloseRead | null | undefined): {
  memo: string | null;
  rollforward: RollforwardBlock | null;
  reconciliation: ReconciliationBlock | null;
  form4797: Form4797Block | null;
} {
  return {
    memo: close?.memo_md ?? null,
    rollforward: close?.rollforward ?? null,
    reconciliation: close?.reconciliation ?? null,
    form4797: close?.form4797 ?? null,
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
