// What the screens make out of the contract types. Pure functions only: no fetch,
// no React, no formatting. Every one of them is unit tested in derive.test.ts, so
// a wrong number on a ticket has one place to look.

import type {
  CloseCheck,
  CloseRead,
  EstimateRef,
  EventDetail,
  EventSummary,
  IdentificationRead,
  ItemClass,
  ItemRecordRead,
  JournalEntryRead,
  OptionKind,
  OptionScoreRead,
  VisionCandidate,
} from "./types";

// Media --------------------------------------------------------------------

/**
 * Image paths come back relative to the backend origin (`/media/17/crop.jpg`),
 * so the page has to put the origin back on before the browser can fetch them.
 */
export function mediaSrc(base: string, url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(url) || url.startsWith("//")) return url;
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? "" : "/"}${url}`;
}

// The ticket ---------------------------------------------------------------

export type TicketFigure = {
  /** Negative when the books lose money, which is most of them. */
  cents: number;
  caption: string;
  estimate: boolean;
  /** False when nothing has been recorded for the event yet. */
  known: boolean;
};

/**
 * The one big number on a ticket, and what it is called.
 *
 * A fixed asset leaves the register at its book value, so the books lose that.
 * Inventory is written off at what it cost. Anything untracked never sat on the
 * books, so the number that matters is what it would have fetched.
 */
export function ticketFigure(
  event: EventSummary,
  record: ItemRecordRead | null | undefined,
): TicketFigure {
  const estimate = isEstimate(event, record);
  const itemClass = record?.class ?? event.class ?? null;

  if (itemClass === "fixed_asset") {
    const book = record?.book_value_cents ?? event.net_book_cents ?? 0;
    return { cents: -book, caption: "book loss", estimate, known: true };
  }
  if (itemClass === "inventory") {
    const cost = record?.cost_basis_cents ?? 0;
    return { cents: -cost, caption: "waste expense", estimate, known: record != null };
  }
  if (itemClass === "untracked") {
    const fmv = record?.fmv?.mid ?? 0;
    return { cents: fmv, caption: "resale value", estimate, known: record != null };
  }
  return { cents: 0, caption: "nothing on the books", estimate, known: false };
}

/**
 * True when the money came out of a model rather than a price list.
 * `is_estimate` is the backend's own answer where it sends one; the item record
 * says the same thing where it does not.
 */
export function isEstimate(
  event: EventSummary,
  record?: ItemRecordRead | null,
): boolean {
  const flag = (event as { is_estimate?: unknown }).is_estimate;
  if (typeof flag === "boolean") return flag;
  return record?.fmv?.source === "model_estimate";
}

/** True when the bin was not allowed to trash the thing it was given. */
export function trashBlocked(options: OptionScoreRead[] | null | undefined): boolean {
  const trash = (options ?? []).find((o) => o.option === "trash");
  return trash != null && !trash.allowed;
}

/** Rank 1 where the engine ranked them, otherwise the best allowed net. */
export function bestOption(
  options: OptionScoreRead[] | null | undefined,
): OptionScoreRead | null {
  const allowed = (options ?? []).filter((o) => o.allowed);
  if (allowed.length === 0) return null;
  const ranked = allowed.find((o) => o.rank === 1);
  if (ranked) return ranked;
  return allowed.reduce((best, o) =>
    o.net_after_tax_cents > best.net_after_tax_cents ? o : best,
  );
}

/** The identification the pipeline settled on, newest final one first. */
export function finalIdentification(
  identifications: IdentificationRead[] | null | undefined,
): IdentificationRead | null {
  const rows = identifications ?? [];
  const finals = rows.filter((row) => row.is_final);
  return finals[finals.length - 1] ?? rows[rows.length - 1] ?? null;
}

/** The posterior arrives as a map. The bars want it sorted and capped. */
export function posteriorCandidates(
  posterior: { [k: string]: number } | null | undefined,
  limit = 4,
): VisionCandidate[] {
  return Object.entries(posterior ?? {})
    .map(([label, p]) => ({ label, p }))
    .sort((a, b) => b.p - a.p)
    .slice(0, limit);
}

// The weight trace ---------------------------------------------------------

export type TracePoint = { t: number; g: number };

export type TraceView = {
  points: TracePoint[];
  baseline_g: number;
  settled_g: number;
  /** Where the step opens and where it settles, in the same seconds as the points. */
  open_t: number;
  settle_t: number;
};

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle] as number;
  return (((sorted[middle - 1] as number) + (sorted[middle] as number)) / 2);
}

/**
 * The trace arrives as pairs of seconds and grams around the step. The two stable
 * medians either side of it give the baseline and the settled weight, and the step
 * is the span between the first sample that leaves one and the first that reaches
 * the other. Shading that span is the whole point of the picture.
 */
export function traceView(pairs: number[][] | null | undefined): TraceView | null {
  const points: TracePoint[] = (pairs ?? [])
    .filter((pair) => pair.length >= 2 && Number.isFinite(pair[0]) && Number.isFinite(pair[1]))
    .map((pair) => ({ t: pair[0] as number, g: pair[1] as number }));
  if (points.length < 2) return null;

  const window = Math.max(1, Math.floor(points.length / 4));
  const baseline_g = median(points.slice(0, window).map((p) => p.g));
  const settled_g = median(points.slice(-window).map((p) => p.g));
  const step = settled_g - baseline_g;
  const first = points[0] as TracePoint;
  const last = points[points.length - 1] as TracePoint;

  if (Math.abs(step) < 1e-6) {
    return { points, baseline_g, settled_g, open_t: first.t, settle_t: last.t };
  }

  const leaves = (g: number) => Math.abs(g - baseline_g) > Math.abs(step) * 0.1;
  const arrives = (g: number) => Math.abs(g - settled_g) < Math.abs(step) * 0.1;
  const opened = points.find((p) => leaves(p.g));
  const settled = points.slice(points.indexOf(opened ?? first)).find((p) => arrives(p.g));

  return {
    points,
    baseline_g,
    settled_g,
    open_t: opened?.t ?? first.t,
    settle_t: settled?.t ?? last.t,
  };
}

// The evidence -------------------------------------------------------------

export type FormulaStep = { label: string; expression: string };

export type EstimateLine = {
  label: string;
  cents: number | null;
  low: number | null;
  high: number | null;
  source: EstimateRef["source"];
};

export type EvidenceBundle = {
  event_id: number;
  title: string;
  crop_url: string | null;
  trace: TraceView | null;
  identification: IdentificationRead | null;
  candidates: VisionCandidate[];
  posterior: VisionCandidate[];
  formula: FormulaStep[];
  rule_ids: string[];
  human_confirmed: boolean;
  estimates: EstimateLine[];
  mass_g: number | null;
  mass_err_g: number | null;
};

function cents(value: number | null | undefined): string {
  const amount = (value ?? 0) / 100;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(amount));
}

function evidenceNumber(entry: JournalEntryRead | undefined, key: string): number | null {
  const raw = entry?.evidence?.[key];
  return typeof raw === "number" ? raw : null;
}

/** The arithmetic behind the big number, with the real values substituted. */
export function formulaFor(detail: EventDetail): FormulaStep[] {
  const record = detail.item_record;
  if (!record) return [];
  const book = (detail.entries ?? []).find((e) => e.basis === "book");
  const tax = (detail.entries ?? []).find((e) => e.basis === "tax_memo");

  if (record.class === "fixed_asset") {
    const cost = evidenceNumber(book, "cost_cents");
    const accum = evidenceNumber(book, "accum_cents");
    const steps: FormulaStep[] = [];
    if (cost !== null && accum !== null) {
      steps.push({
        label: "Book value",
        expression: `${cents(cost)} cost - ${cents(accum)} accumulated = ${cents(record.book_value_cents)} book value`,
      });
    } else {
      steps.push({ label: "Book value", expression: cents(record.book_value_cents) });
    }
    const deduction = evidenceNumber(tax, "tax_loss_cents");
    steps.push({
      label: "Tax basis",
      expression: `${cents(record.tax_basis_cents)}, so the deduction is ${cents(deduction ?? 0)}`,
    });
    steps.push({
      label: "Difference",
      expression: `${cents((record.book_value_cents ?? 0) - (record.tax_basis_cents ?? 0))} the books lose that the return does not`,
    });
    return steps;
  }

  if (record.class === "inventory") {
    return [
      {
        label: "Cost basis",
        expression: `${cents(record.cost_basis_cents)} at ${Math.round(record.mass_g)} g`,
      },
      { label: "Tax", expression: "Already in cost of goods sold, so there is no second entry." },
    ];
  }

  return [
    { label: "Fair market value", expression: cents(record.fmv?.mid) },
    { label: "Book value", expression: "Nothing. It was never on the register." },
  ];
}

/** Every estimate on the record, each one carrying where it came from. */
export function estimateLines(record: ItemRecordRead | null | undefined): EstimateLine[] {
  if (!record) return [];
  const lines: EstimateLine[] = [];
  const push = (label: string, ref: EstimateRef | null | undefined) => {
    if (!ref || ref.mid == null) return;
    lines.push({
      label,
      cents: ref.mid,
      low: ref.low ?? null,
      high: ref.high ?? null,
      source: ref.source ?? null,
    });
  };
  push("Fair market value", record.fmv);
  push("Repair", record.repair);
  if (record.replacement_cents != null) {
    lines.push({
      label: "Replacement",
      cents: record.replacement_cents,
      low: null,
      high: null,
      source: asEstimateSource(record.replacement_source),
    });
  }
  if (record.scrap_cents != null) {
    lines.push({
      label: "Scrap",
      cents: record.scrap_cents,
      low: null,
      high: null,
      source: asEstimateSource(record.scrap_source),
    });
  }
  return lines;
}

/** A source column is a plain string on the wire. Only the four known ones are shown. */
export function asEstimateSource(raw: string | null | undefined): EstimateRef["source"] {
  if (raw === "catalog" || raw === "register" || raw === "model_estimate" || raw === "human") {
    return raw;
  }
  return null;
}

/** Everything the drawer and the event page draw, out of one event read. */
export function evidenceBundle(detail: EventDetail): EvidenceBundle {
  const identification = finalIdentification(detail.identifications);
  const byHand = (detail.identifications ?? []).some((row) => row.method === "human");
  const ruleIds = new Set<string>();
  for (const option of detail.options ?? []) {
    for (const id of option.rule_ids ?? []) ruleIds.add(id);
  }
  return {
    event_id: detail.event.id,
    title: detail.event.label ?? `Ticket ${detail.event.id}`,
    crop_url: detail.event.crop_url ?? null,
    trace: traceView(detail.trace),
    identification,
    candidates: identification?.candidates ?? [],
    posterior: posteriorCandidates(identification?.posterior),
    formula: formulaFor(detail),
    rule_ids: [...ruleIds],
    human_confirmed: byHand || (detail.corrections ?? []).length > 0,
    estimates: estimateLines(detail.item_record),
    mass_g: detail.event.mass_g ?? null,
    mass_err_g: detail.event.mass_err_g ?? null,
  };
}

// The close report ---------------------------------------------------------

export type WriteOffRow = { label: string; count: number; mass_g: number; cents: number };
export type DisposalRow = {
  event_id: number | null;
  tag: string | null;
  description: string;
  book_loss_cents: number;
  tax_loss_cents: number;
};
export type MissedRow = { option: OptionKind | null; cents: number };
export type GhostRow = {
  tag: string | null;
  description: string;
  location: string | null;
  event_id: number | null;
};

export type Sustainability = {
  kg_to_landfill: number;
  kg_diverted_if_followed: number;
  kg_co2e_actual: number;
  kg_co2e_best: number;
  kg_ewaste: number;
  cheapest_equals_greenest_pct: number;
  events_without_carbon: number;
};

export type CloseReport = {
  id: number;
  period_start: string;
  period_end: string;
  created_at: string;
  needs_review: boolean;
  write_offs: WriteOffRow[];
  write_off_total_cents: number;
  disposals: DisposalRow[];
  disposal_book_loss_cents: number;
  disposal_tax_loss_cents: number;
  missed: MissedRow[];
  missed_total_cents: number;
  sustainability: Sustainability | null;
  ghosts: GhostRow[];
  checks: CloseCheck[];
  investigation: string | null;
};

type Bag = { [k: string]: unknown };

function bag(value: unknown): Bag {
  return value != null && typeof value === "object" && !Array.isArray(value)
    ? (value as Bag)
    : {};
}

function rowsOf(value: unknown): Bag[] {
  const list = bag(value)["rows"];
  return Array.isArray(list) ? list.map(bag) : [];
}

function num(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function id(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

const MISSED_OPTIONS: { key: string; option: OptionKind }[] = [
  { key: "would_have_donated_cents", option: "donate" },
  { key: "would_have_resold_cents", option: "resell" },
  { key: "would_have_repaired_cents", option: "repair" },
  { key: "would_have_recycled_cents", option: "recycle" },
];

/**
 * The close arrives with its totals in an open map, because the close writes a
 * whole report and not a fixed row. This reads the parts the statement prints and
 * ignores the rest, so a new key in the report cannot break the page.
 */
export function closeReport(read: CloseRead): CloseReport {
  const totals = bag(read.totals);
  const writeOffs = bag(totals["write_offs"]);
  const disposals = bag(totals["asset_disposals"]);
  const missed = bag(totals["missed_opportunity"]);
  const green = bag(totals["sustainability"]);
  const ghosts = bag(totals["ghost_assets"]);
  const byOption = bag(missed["by_option"]);

  return {
    id: read.id,
    period_start: read.period_start,
    period_end: read.period_end,
    created_at: read.created_at,
    needs_review: (read.checks ?? []).some((c) => c.result !== "pass"),
    write_offs: rowsOf(writeOffs).map((row) => ({
      label: str(row["label"]) ?? "Unnamed item",
      count: num(row["count"]),
      mass_g: num(row["mass_g"]),
      cents: num(row["cents"]),
    })),
    write_off_total_cents: num(writeOffs["total_cents"]),
    disposals: rowsOf(disposals).map((row) => ({
      event_id: id(row["event_id"]),
      tag: str(row["tag"]),
      description: str(row["description"]) ?? str(row["label"]) ?? "Unnamed asset",
      book_loss_cents: num(row["book_loss_cents"]),
      tax_loss_cents: num(row["tax_loss_cents"]),
    })),
    disposal_book_loss_cents: num(disposals["book_loss_cents"]),
    disposal_tax_loss_cents: num(disposals["tax_loss_cents"]),
    missed: MISSED_OPTIONS.filter((entry) => num(byOption[entry.key]) !== 0).map((entry) => ({
      option: entry.option,
      cents: num(byOption[entry.key]),
    })),
    missed_total_cents: num(missed["total_cents"]),
    sustainability: Object.keys(green).length
      ? {
          kg_to_landfill: num(green["kg_to_landfill"]),
          kg_diverted_if_followed: num(green["kg_diverted_if_followed"]),
          kg_co2e_actual: num(green["kg_co2e_actual"]),
          kg_co2e_best: num(green["kg_co2e_best"]),
          kg_ewaste: num(green["kg_ewaste"]),
          cheapest_equals_greenest_pct: num(green["cheapest_equals_greenest_pct"]),
          events_without_carbon: num(green["events_without_carbon"]),
        }
      : null,
    ghosts: rowsOf(ghosts).map((row) => ({
      tag: str(row["tag"]),
      description: str(row["description"]) ?? "Unnamed asset",
      location: str(row["location"]),
      event_id: id(row["event_id"]),
    })),
    checks: read.checks ?? [],
    investigation: read.investigation_md ?? null,
  };
}

/**
 * A check is identified by a key, and the statement needs a name for it.
 * An id nobody has named reads as words rather than as a key.
 */
const CHECK_NAMES: { [k: string]: string } = {
  mass_conservation: "Mass conservation",
  ledger_balance: "Ledger balance",
  register_consistency: "Register consistency",
  unresolved_asks: "Unresolved asks",
  low_confidence_share: "Settled by a person",
};

export function checkName(check: CloseCheck): string {
  const known = CHECK_NAMES[check.id];
  if (known) return known;
  const words = check.id.replace(/[_-]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Which numbers a check prints under it, in the order the balance is read. */
const CHECK_NUMBER_WORDS: { [k: string]: string } = {
  scale_reads_g: "Scale reads",
  tickets_g: "Tickets sum to",
  difference_g: "Difference",
  tolerance_g: "Allowed",
  tickets: "Tickets",
  entries: "Entries",
  unbalanced_entries: "Entries that do not balance",
  debit_cents: "Debits",
  credit_cents: "Credits",
  difference_cents: "Difference",
  disposed_assets: "Assets marked disposed",
  missing_entries: "Without a disposal entry",
  duplicate_entries: "With more than one entry",
  asking: "Still waiting on an answer",
  tosses: "Tosses",
  settled_by_person: "Settled by a person",
};

export type CheckNumber = { label: string; value: number; kind: "grams" | "cents" | "count" };

export function checkNumbers(check: CloseCheck): CheckNumber[] {
  return Object.entries(check.numbers ?? {})
    .filter(([key]) => key in CHECK_NUMBER_WORDS)
    .map(([key, value]) => ({
      label: CHECK_NUMBER_WORDS[key] as string,
      value,
      kind: key.endsWith("_g") ? "grams" : key.endsWith("_cents") ? "cents" : "count",
    }));
}

// The class of a thing, said the way a person would ---------------------------

const CLASS_WORDS: { [k in ItemClass]: string } = {
  fixed_asset: "Tagged asset",
  inventory: "Inventory",
  untracked: "Untracked",
};

export function classWords(value: ItemClass | null | undefined): string | null {
  return value ? CLASS_WORDS[value] : null;
}

/** The sentence under the T-accounts, which depends on what was thrown away. */
export function bookVsTax(itemClass: ItemClass | null | undefined): string {
  if (itemClass === "fixed_asset") {
    return "The books take the loss now. The tax return already took it when the item was bought, which is why the tax side is smaller.";
  }
  if (itemClass === "inventory") {
    return "Inventory cost flows through cost of goods sold, so there is no separate tax entry.";
  }
  return "Nothing was on the books for this, so there is no entry on either side.";
}
