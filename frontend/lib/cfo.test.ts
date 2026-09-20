import assert from "node:assert/strict";
import test from "node:test";
import { blocksOf, reconciliationFoots, rollforwardParts } from "./cfo.ts";
import type { RollforwardRow } from "./types.ts";

const disposed: RollforwardRow = {
  opening_cost_cents: 12000,
  additions_cents: 0,
  disposals_cost_cents: 12000,
  closing_cost_cents: 0,
  opening_accum_cents: 10000,
  depreciation_cents: 0,
  disposals_accum_cents: 10000,
  closing_accum_cents: 0,
  opening_nbv_cents: 2000,
  closing_nbv_cents: 0,
};

test("a rollforward line foots when opening plus the movements is closing", () => {
  const parts = rollforwardParts(disposed);
  assert.equal(parts.opening, 2000);
  assert.equal(parts.disposals, 2000);
  assert.equal(parts.closing, 0);
  assert.equal(parts.foots, true);
});

test("a rollforward line that does not foot says so", () => {
  assert.equal(rollforwardParts({ ...disposed, closing_nbv_cents: 500 }).foots, false);
});

test("a line with no net book value column is worked out from cost and accumulated", () => {
  const parts = rollforwardParts({
    opening_cost_cents: 18900,
    opening_accum_cents: 5250,
    depreciation_cents: 525,
    closing_cost_cents: 18900,
    closing_accum_cents: 5775,
  });
  assert.equal(parts.opening, 13650);
  assert.equal(parts.closing, 13125);
  assert.equal(parts.foots, true);
});

test("the M-1 block reconciles when the book loss less the differences is the tax loss", () => {
  assert.equal(
    reconciliationFoots({ book_loss_cents: 2062, differences_cents: 2000, tax_loss_cents: 62 }),
    true,
  );
  assert.equal(
    reconciliationFoots({ book_loss_cents: 2062, differences_cents: 2000, tax_loss_cents: 100 }),
    false,
  );
});

test("the backend's own answer about the footing wins over recomputing it", () => {
  assert.equal(
    reconciliationFoots({
      ties: false,
      book_loss_cents: 2062,
      differences_cents: 2000,
      tax_loss_cents: 62,
    }),
    false,
  );
});

test("a close written before the blocks existed reads as four nulls, not a crash", () => {
  const blocks = blocksOf({
    id: 1,
    created_at: "2026-09-19T14:45:00",
    period_start: "2026-09-19",
    period_end: "2026-09-19",
    status: "needs_review",
  });
  assert.equal(blocks.memo, null);
  assert.equal(blocks.rollforward, null);
  assert.equal(blocks.reconciliation, null);
  assert.equal(blocks.form4797, null);
  assert.equal(blocksOf(null).memo, null);
});
