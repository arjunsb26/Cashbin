import assert from "node:assert/strict";
import test from "node:test";
import {
  asEstimateSource,
  bestOption,
  bookVsTax,
  checkName,
  checkNumbers,
  classWords,
  closeReport,
  estimateLines,
  evidenceBundle,
  formulaFor,
  isEstimate,
  mediaSrc,
  posteriorCandidates,
  ticketFigure,
  traceView,
  trashBlocked,
} from "./derive.ts";
import type {
  CloseRead,
  EventDetail,
  EventSummary,
  ItemRecordRead,
  OptionScoreRead,
} from "./types.ts";

function event(over: Partial<EventSummary> = {}): EventSummary {
  return {
    id: 1,
    created_at: "2026-09-19T14:24:00",
    kind: "toss",
    status: "posted",
    mass_g: 780,
    mass_err_g: 3,
    label: "mechanical keyboard",
    class: "fixed_asset",
    crop_url: null,
    crop_quality: "ok",
    net_book_cents: 2000,
    best_option: "resell",
    saved_if_followed_cents: 1200,
    round_id: 4,
    ...over,
  };
}

function record(over: Partial<ItemRecordRead> = {}): ItemRecordRead {
  return {
    event_id: 1,
    label: "mechanical keyboard",
    class: "fixed_asset",
    mass_g: 780,
    condition: "working",
    material_mix: {},
    regulatory_flags: [],
    book_value_cents: 2000,
    tax_basis_cents: 0,
    asset_id: 2,
    cost_basis_cents: 0,
    fmv: { low: null, mid: null, high: null, source: null },
    repair: { low: null, mid: null, high: null, source: null },
    replacement_cents: null,
    replacement_source: null,
    scrap_cents: null,
    scrap_source: null,
    ...over,
  };
}

function option(over: Partial<OptionScoreRead>): OptionScoreRead {
  return {
    id: 1,
    event_id: 1,
    option: "trash",
    allowed: true,
    blocked_reason: null,
    cash_cents: 0,
    tax_effect_cents: 0,
    net_after_tax_cents: 0,
    kg_co2e: null,
    kg_landfill: 0,
    needs_human_review: false,
    notes: [],
    rule_ids: [],
    rank: null,
    ...over,
  };
}

test("media paths get the backend origin back on", () => {
  assert.equal(mediaSrc("https://localhost:8443", "/media/17/crop.jpg"), "https://localhost:8443/media/17/crop.jpg");
  assert.equal(mediaSrc("https://localhost:8443/", "media/17/crop.jpg"), "https://localhost:8443/media/17/crop.jpg");
  assert.equal(mediaSrc("https://localhost:8443", null), null);
  assert.equal(mediaSrc("https://localhost:8443", "https://cdn/x.jpg"), "https://cdn/x.jpg");
  assert.equal(mediaSrc("https://localhost:8443", "data:image/png;base64,aa"), "data:image/png;base64,aa");
});

test("a tagged asset loses its book value", () => {
  const figure = ticketFigure(event(), record());
  assert.equal(figure.cents, -2000);
  assert.equal(figure.caption, "book loss");
  assert.equal(figure.known, true);
});

test("a tagged asset reads from the summary when there is no record yet", () => {
  const figure = ticketFigure(event({ net_book_cents: 1500 }), null);
  assert.equal(figure.cents, -1500);
});

test("inventory is written off at what it cost, not at its book value", () => {
  const figure = ticketFigure(
    event({ class: "inventory", net_book_cents: 0, label: "bagel" }),
    record({ class: "inventory", book_value_cents: 0, cost_basis_cents: 33 }),
  );
  assert.equal(figure.cents, -33);
  assert.equal(figure.caption, "waste expense");
});

test("something untracked shows what it was worth", () => {
  const figure = ticketFigure(
    event({ class: "untracked", net_book_cents: 0 }),
    record({
      class: "untracked",
      book_value_cents: 0,
      fmv: { low: 600, mid: 800, high: 1100, source: "model_estimate" },
    }),
  );
  assert.equal(figure.cents, 800);
  assert.equal(figure.caption, "resale value");
  assert.equal(figure.estimate, true);
});

test("an event with nothing recorded says so rather than printing zero", () => {
  const figure = ticketFigure(event({ class: null, status: "detected", label: null }), null);
  assert.equal(figure.known, false);
});

test("is_estimate wins over the record when the backend sends it", () => {
  const withFlag = { ...event(), is_estimate: false } as EventSummary;
  const fromModel = record({ fmv: { low: 1, mid: 2, high: 3, source: "model_estimate" } });
  assert.equal(isEstimate(withFlag, fromModel), false);
  assert.equal(isEstimate(event(), fromModel), true);
  assert.equal(isEstimate(event(), record()), false);
});

test("a blocked trash row is what makes a ticket blocked", () => {
  assert.equal(trashBlocked([option({ option: "trash", allowed: false })]), true);
  assert.equal(trashBlocked([option({ option: "trash", allowed: true })]), false);
  assert.equal(trashBlocked([]), false);
  assert.equal(trashBlocked(undefined), false);
});

test("the best option is rank one, or the best allowed net without a rank", () => {
  const ranked = bestOption([
    option({ option: "trash", rank: 2, net_after_tax_cents: 100 }),
    option({ option: "resell", rank: 1, net_after_tax_cents: 50 }),
  ]);
  assert.equal(ranked?.option, "resell");

  const unranked = bestOption([
    option({ option: "trash", net_after_tax_cents: 10 }),
    option({ option: "recycle", net_after_tax_cents: 40 }),
  ]);
  assert.equal(unranked?.option, "recycle");

  assert.equal(bestOption([option({ option: "trash", allowed: false })]), null);
});

test("the posterior map becomes sorted candidates", () => {
  const rows = posteriorCandidates({ a: 0.2, b: 0.5, c: 0.3 }, 2);
  assert.deepEqual(rows, [
    { label: "b", p: 0.5 },
    { label: "c", p: 0.3 },
  ]);
  assert.deepEqual(posteriorCandidates(undefined), []);
});

test("the trace finds the baseline, the settle and the step between them", () => {
  const pairs: number[][] = [];
  for (let i = 0; i < 40; i += 1) {
    pairs.push([i * 0.1, i < 20 ? 2000 : 2100]);
  }
  const view = traceView(pairs);
  assert.ok(view);
  assert.equal(view.baseline_g, 2000);
  assert.equal(view.settled_g, 2100);
  assert.ok(view.open_t <= view.settle_t);
  assert.equal(view.points.length, 40);
});

test("a trace with nothing usable in it draws nothing", () => {
  assert.equal(traceView([]), null);
  assert.equal(traceView(undefined), null);
  assert.equal(traceView([[0, 1]]), null);
});

test("a flat trace still gives a view", () => {
  const view = traceView([
    [0, 2000],
    [0.1, 2000],
    [0.2, 2000],
    [0.3, 2000],
  ]);
  assert.ok(view);
  assert.equal(view.baseline_g, 2000);
  assert.equal(view.settled_g, 2000);
});

test("only the four known estimate sources are shown", () => {
  assert.equal(asEstimateSource("catalog"), "catalog");
  assert.equal(asEstimateSource("model_estimate"), "model_estimate");
  assert.equal(asEstimateSource("something else"), null);
  assert.equal(asEstimateSource(null), null);
});

test("every estimate on a record carries where it came from", () => {
  const lines = estimateLines(
    record({
      fmv: { low: 2800, mid: 3200, high: 3800, source: "model_estimate" },
      replacement_cents: 12000,
      replacement_source: "register",
      scrap_cents: 42,
      scrap_source: "catalog",
    }),
  );
  assert.deepEqual(
    lines.map((l) => [l.label, l.cents, l.source]),
    [
      ["Fair market value", 3200, "model_estimate"],
      ["Replacement", 12000, "register"],
      ["Scrap", 42, "catalog"],
    ],
  );
  assert.deepEqual(estimateLines(null), []);
});

function detail(over: Partial<EventDetail> = {}): EventDetail {
  return {
    event: event(),
    trace: [],
    frame_before_url: null,
    frame_after_url: null,
    frame_peak_url: null,
    identifications: [],
    item_record: record(),
    options: [],
    entries: [],
    corrections: [],
    ...over,
  };
}

test("the arithmetic substitutes the real values from the entry", () => {
  const steps = formulaFor(
    detail({
      entries: [
        {
          id: 1,
          event_id: 1,
          close_id: null,
          posted_at: "2026-09-19T14:24:00",
          memo: "Dispose",
          basis: "book",
          lines: [],
          evidence: { cost_cents: 12000, accum_cents: 10000 },
        },
      ],
    }),
  );
  assert.equal(steps[0]?.expression, "120.00 cost - 100.00 accumulated = 20.00 book value");
});

test("inventory says what it cost and why there is no tax entry", () => {
  const steps = formulaFor(
    detail({ item_record: record({ class: "inventory", cost_basis_cents: 33, mass_g: 95 }) }),
  );
  assert.equal(steps[0]?.expression, "0.33 at 95 g");
  assert.equal(steps.length, 2);
});

test("an event with no record has no arithmetic to show", () => {
  assert.deepEqual(formulaFor(detail({ item_record: null })), []);
});

test("the evidence bundle collects the rule ids once each", () => {
  const bundle = evidenceBundle(
    detail({
      options: [
        option({ option: "trash", rule_ids: ["EWASTE"] }),
        option({ option: "recycle", rule_ids: ["EWASTE", "ABANDON"] }),
      ],
      corrections: [
        {
          id: 1,
          event_id: 1,
          field: "label",
          old_value: "a",
          new_value: "b",
          by: "person",
          created_at: "2026-09-19T14:30:00",
        },
      ],
    }),
  );
  assert.deepEqual(bundle.rule_ids, ["EWASTE", "ABANDON"]);
  assert.equal(bundle.human_confirmed, true);
  assert.equal(bundle.title, "mechanical keyboard");
});

test("an unlabelled event is titled by its ticket number", () => {
  const bundle = evidenceBundle(detail({ event: event({ label: null }) }));
  assert.equal(bundle.title, "Ticket 1");
  assert.equal(bundle.human_confirmed, false);
});

const CLOSE: CloseRead = {
  id: 1,
  period_start: "2026-09-19",
  period_end: "2026-09-19",
  created_at: "2026-09-19T14:45:00",
  status: "needs_review",
  investigation_md: "Recount 103 and 104.",
  totals: {
    write_offs: {
      rows: [{ label: "bagel", count: 1, mass_g: 95, cents: 33 }],
      total_cents: 33,
    },
    asset_disposals: {
      rows: [
        {
          event_id: 102,
          tag: "bb-0002",
          description: "Mechanical keyboard",
          book_loss_cents: 2000,
          tax_loss_cents: 0,
        },
      ],
      book_loss_cents: 2000,
      tax_loss_cents: 0,
    },
    missed_opportunity: {
      total_cents: 4180,
      by_option: {
        would_have_donated_cents: 14,
        would_have_resold_cents: 3960,
        would_have_repaired_cents: 0,
        would_have_recycled_cents: 206,
      },
    },
    sustainability: { kg_to_landfill: 0.107, cheapest_equals_greenest_pct: 75 },
    ghost_assets: { rows: [{ tag: "bb-0006", description: "Desk monitor 24 inch" }] },
  },
  checks: [{ id: "mass_conservation", result: "fail", detail: "x", numbers: { difference_g: 14 } }],
  report: {},
};

test("the close report reads the parts the statement prints", () => {
  const report = closeReport(CLOSE);
  assert.equal(report.write_offs.length, 1);
  assert.equal(report.write_off_total_cents, 33);
  assert.equal(report.disposals[0]?.tag, "bb-0002");
  assert.equal(report.disposal_book_loss_cents, 2000);
  assert.equal(report.sustainability?.kg_to_landfill, 0.107);
  assert.equal(report.ghosts[0]?.description, "Desk monitor 24 inch");
  assert.equal(report.needs_review, true);
  assert.equal(report.investigation, "Recount 103 and 104.");
});

test("an option worth nothing is left off the missed list", () => {
  const report = closeReport(CLOSE);
  assert.deepEqual(
    report.missed.map((m) => m.option),
    ["donate", "resell", "recycle"],
  );
});

test("a close with an empty report does not throw", () => {
  const report = closeReport({ ...CLOSE, totals: {}, checks: [], investigation_md: null });
  assert.deepEqual(report.write_offs, []);
  assert.equal(report.sustainability, null);
  assert.equal(report.needs_review, false);
});

test("a check is named, and an unnamed one reads as words", () => {
  assert.equal(checkName({ id: "mass_conservation", result: "pass" }), "Mass conservation");
  assert.equal(checkName({ id: "new_check_here", result: "pass" }), "New check here");
});

test("only the numbers a check has words for are printed", () => {
  const numbers = checkNumbers({
    id: "mass_conservation",
    result: "fail",
    numbers: { difference_g: 14, tolerance_g: 21, internal_thing: 1 },
  });
  assert.deepEqual(
    numbers.map((n) => [n.label, n.kind]),
    [
      ["Difference", "grams"],
      ["Allowed", "grams"],
    ],
  );
});

test("the class and the book against tax sentence are said in plain words", () => {
  assert.equal(classWords("fixed_asset"), "Tagged asset");
  assert.equal(classWords(null), null);
  assert.ok(bookVsTax("inventory").includes("cost of goods sold"));
  assert.ok(bookVsTax(null).includes("no entry"));
});
