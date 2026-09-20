// What the screens make out of the contract types. Pure functions only: no fetch,
// no React, no formatting. Every one of them is unit tested in derive.test.ts, so
// a wrong number on a ticket has one place to look.

import type {
  CategoryStat,
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
  RuleRead,
  StatsAverages,
  StatsBucket,
  StatsResponse,
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
    // The estimate leaves the critical path, so a ticket can be labelled and
    // classed with no value yet. Nothing on the books is not the same as zero.
    const fmv = record?.fmv?.mid ?? null;
    return {
      cents: fmv ?? 0,
      caption: "resale value",
      estimate,
      known: record != null && fmv != null,
    };
  }
  return { cents: 0, caption: "nothing on the books", estimate, known: false };
}

/**
 * What a toss means, in the words that fit its class. PLAN.md 21a item 41.
 *
 * "Wasted $3.00" for something that was bought to be used up, "Written off,
 * $65.00 book loss" for a tagged asset leaving the register, "Worth about
 * $12.00" for anything that was never on the books, and the carbon for
 * packaging, where a cardboard box's forty cents is noise and the emissions are
 * the story. The figure is printed positive, because the words carry the sign.
 */
export type HeadlineKind = "wasted" | "written off" | "worth" | "carbon" | "unknown" | "given";

export type Headline = {
  kind: HeadlineKind;
  /** The words before the figure. */
  lead: string;
  /** The words after it, a finance term where the class has one. */
  trail: string;
  /** The money figure, positive as printed. Null when the figure is carbon. */
  cents: number | null;
  /** The carbon figure in kg, when the figure is carbon. */
  kg: number | null;
  /** The figure already written out, when the backend sent the whole sentence. */
  text?: string;
  /** True when this is a loss, so the figure prints in red ink. */
  loss: boolean;
  /** False when nothing has been valued for the ticket yet. */
  known: boolean;
  estimate: boolean;
};

/**
 * Materials that are packaging rather than the thing inside it. A row whose whole
 * mix is on this list was bought to be thrown away, so the money is pennies and
 * the carbon is what a person can act on.
 */
const PACKAGING_MATERIALS = new Set([
  "corrugated_containers",
  "mixed_paper",
  "office_paper",
  "magazines",
  "newspaper",
  "mixed_plastics",
  "pet",
  "hdpe",
  "ldpe",
  "glass",
  "aluminum_cans",
  "steel_cans",
]);

/** True when every material on the item record is packaging and none of it is food. */
export function isPackaging(record: ItemRecordRead | null | undefined): boolean {
  if (!record || record.class !== "inventory") return false;
  if ((record.regulatory_flags ?? []).includes("food")) return false;
  const mix = Object.entries(record.material_mix ?? {}).filter(([, share]) => share > 0);
  if (mix.length === 0) return false;
  return mix.every(([material]) => PACKAGING_MATERIALS.has(material));
}

/**
 * The backend's own headline, split around its money so the figure can still be
 * the big condensed one. "Written off, $65.00 book loss" becomes the words before
 * it, the money, and the words after. A sentence with no money in it is printed
 * whole, at body size, because inventing a figure for it would be a lie.
 */
export function splitHeadline(text: string): { lead: string; money: string; trail: string } {
  const clean = text.replace(/\s+/g, " ").trim().slice(0, 120);
  const found = /[-(]?\$\s?[\d,]+(?:\.\d{2})?\)?/.exec(clean);
  if (!found) return { lead: clean, money: "", trail: "" };
  return {
    lead: clean.slice(0, found.index).trim(),
    money: found[0].replace(/\s/g, ""),
    trail: clean.slice(found.index + found[0].length).trim(),
  };
}

/** The headline string the backend sends, when it sends one. Model words, so capped. */
export function headlineText(event: EventSummary): string | null {
  const raw = (event as { headline?: unknown }).headline;
  if (typeof raw !== "string") return null;
  const text = raw.replace(/\s+/g, " ").trim().slice(0, 120);
  return text.length > 0 ? text : null;
}

export function ticketHeadline(
  event: EventSummary,
  record: ItemRecordRead | null | undefined,
  options?: OptionScoreRead[] | null,
): Headline {
  const figure = ticketFigure(event, record);
  // The backend's own words win where it sends them. PLAN.md 21a item 41 is the
  // same rule on both sides, and one sentence beats two that can drift apart.
  const given = headlineText(event);
  if (given !== null) {
    const parts = splitHeadline(given);
    return {
      kind: "given",
      lead: parts.lead,
      trail: parts.trail,
      text: parts.money,
      cents: null,
      kg: null,
      loss: /loss|wasted|written off/i.test(given),
      known: true,
      estimate: isEstimate(event, record),
    };
  }
  const base = { estimate: figure.estimate, known: figure.known };
  const itemClass = record?.class ?? event.class ?? null;

  if (itemClass === "fixed_asset") {
    return {
      ...base,
      kind: "written off",
      lead: "Written off,",
      trail: "book loss",
      cents: Math.abs(figure.cents),
      kg: null,
      loss: true,
    };
  }
  if (itemClass === "inventory") {
    if (isPackaging(record)) {
      const best = bestOption(options);
      const kg = best ? co2eAvoided(best) : null;
      if (kg != null) {
        return {
          ...base,
          kind: "carbon",
          lead: `${formatBestWord(best?.option)} it and you keep`,
          trail: "kg CO2e out of the air",
          cents: null,
          kg,
          loss: false,
          known: true,
        };
      }
    }
    return {
      ...base,
      kind: "wasted",
      lead: "Wasted",
      trail: "",
      cents: Math.abs(figure.cents),
      kg: null,
      loss: true,
    };
  }
  if (itemClass === "untracked") {
    return {
      ...base,
      kind: "worth",
      lead: "Worth about",
      trail: "",
      cents: Math.abs(figure.cents),
      kg: null,
      loss: false,
    };
  }
  return {
    ...base,
    kind: "unknown",
    lead: "",
    trail: "nothing on the books",
    cents: null,
    kg: null,
    loss: false,
    known: false,
  };
}

/** The verb for an option, at the head of a sentence. */
function formatBestWord(option: OptionKind | null | undefined): string {
  if (option === "recycle") return "Recycle";
  if (option === "resell") return "Resell";
  if (option === "donate") return "Donate";
  if (option === "repair") return "Repair";
  return "Bin";
}

/**
 * True when the bin was already the right answer, so the option table has nothing
 * to argue about and collapses to the one row. PLAN.md 21a item 37: advice is
 * spoken only when it matters. This is the engine's own tone rule, so the ticket,
 * the LCD and the phone agree on when to stay quiet.
 */
export function fineToBin(
  options: OptionScoreRead[] | null | undefined,
  thresholds?: { tone_co2e_kg?: number | null; tie_break_cents?: number | null } | null,
): boolean {
  return (options ?? []).length > 0 && ticketTone(options, thresholds) === "kept";
}

/**
 * What the tape prints for a row.
 *
 * `posted_cents` is what the journal actually posted against the ticket, which is
 * the honest number for a printed tape: a ticket whose entry moved nothing says
 * nothing. The field is newer than this screen, so where the backend does not send
 * it the ticket's own figure stands in and the tape reads exactly as it did.
 */
export function tapeAmount(
  event: EventSummary,
  record: ItemRecordRead | null | undefined,
): TicketFigure {
  const posted = event.posted_cents;
  if (typeof posted === "number") {
    const figure = ticketFigure(event, record);
    return { ...figure, cents: posted, known: true };
  }
  return ticketFigure(event, record);
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

/** The three tones the LCD, the phone sheet and now the ticket share. */
export type Tone = "kept" | "caution" | "red";

/** Defaults matching the engine's own, used until the settings read lands. */
export const TONE_CO2E_KG = 0.02;
export const TIE_BREAK_CENTS = 50;

/**
 * The tone of a ticket, by the same rule the engine uses for the LCD.
 *
 * Red when the bin was not allowed to take the thing at all. Green only when the
 * bin was already a fine answer, which means it was the best option, or the best
 * option beat it by less than the money tie break and by less than the carbon
 * threshold. Everything else is amber, so an option worth the same money and much
 * less carbon still says a better answer existed. An unknown carbon figure never
 * buys a green tone.
 *
 * Null when the ticket has no options yet, because a colour with nothing behind
 * it is a colour without meaning.
 */
export function ticketTone(
  options: OptionScoreRead[] | null | undefined,
  thresholds?: { tone_co2e_kg?: number | null; tie_break_cents?: number | null } | null,
): Tone | null {
  const rows = options ?? [];
  if (rows.length === 0) return null;
  const trash = rows.find((o) => o.option === "trash") ?? null;
  if (trash !== null && !trash.allowed) return "red";
  const best = bestOption(rows);
  if (best === null || trash === null) return "caution";
  if (best.option === "trash") return "kept";

  const tieBreak = thresholds?.tie_break_cents ?? TIE_BREAK_CENTS;
  if (best.net_after_tax_cents - trash.net_after_tax_cents >= tieBreak) return "caution";
  if (best.kg_co2e == null || trash.kg_co2e == null) return "caution";
  const carbon = thresholds?.tone_co2e_kg ?? TONE_CO2E_KG;
  if (Math.abs(best.kg_co2e - trash.kg_co2e) >= carbon) return "caution";
  return "kept";
}

/**
 * Carbon the option avoids, as a positive number.
 *
 * The engine's WARM factors are negative for anything that keeps material out of
 * the ground, which reads as nonsense on a page. The backend sends the positive
 * form where it has it; where it does not, flipping the sign is the same figure.
 */
export function co2eAvoided(option: OptionScoreRead): number | null {
  if (option.kg_co2e_avoided != null) return option.kg_co2e_avoided;
  if (option.kg_co2e == null) return null;
  return -option.kg_co2e;
}

/** The rules by the code the engine cites, so a drawer can look one up. */
export function ruleMap(rules: RuleRead[] | null | undefined): Map<string, RuleRead> {
  return new Map((rules ?? []).map((rule) => [rule.id, rule]));
}

/** The identification the pipeline settled on, newest final one first. */
export function finalIdentification(
  identifications: IdentificationRead[] | null | undefined,
): IdentificationRead | null {
  const rows = identifications ?? [];
  const finals = rows.filter((row) => row.is_final);
  return finals[finals.length - 1] ?? rows[rows.length - 1] ?? null;
}

/**
 * What the vision call saw, with its own answer in the list.
 *
 * The candidate list is the alternatives it weighed, so the label it settled on is
 * not in it. A bar chart headed "from the photo alone" that leaves out the winner
 * is a lie, so the winner goes back in at its own confidence.
 */
export function visionCandidates(
  identification: IdentificationRead | null | undefined,
): VisionCandidate[] {
  const rows = identification?.candidates ?? [];
  const label = identification?.label;
  const merged =
    label && !rows.some((row) => row.label === label)
      ? [{ label, p: identification?.confidence ?? 0 }, ...rows]
      : [...rows];
  return merged.sort((a, b) => b.p - a.p);
}

/** The posterior arrives as a map. The bars want it sorted and capped. */
export function posteriorCandidates(
  posterior: { [k: string]: number } | null | undefined,
  limit = 4,
): VisionCandidate[] {
  return Object.entries(posterior ?? {})
    .filter(([label]) => !isMarker(label))
    .map(([label, p]) => ({ label, p }))
    .sort((a, b) => b.p - a.p)
    .slice(0, limit);
}

/**
 * The posterior map carries the odd key that says how the decision was made
 * rather than what the thing was. A validated label is letters, digits, spaces
 * and hyphens, so a key with an underscore in it is never a label and is never
 * drawn as a bar or offered as an answer.
 */
function isMarker(key: string): boolean {
  return key.includes("_");
}

/**
 * True when the decision was made because the top two answers come out the same
 * in the books, which is why a ticket that looks uncertain did not ask.
 */
export function sameTreatment(
  posterior: { [k: string]: number } | null | undefined,
): boolean {
  return Object.keys(posterior ?? {}).includes("same_treatment");
}

/**
 * The question a ticket is waiting on, rebuilt from what has been read.
 *
 * `ask.opened` only reaches a dashboard that was already open. A page opened or
 * reloaded while a ticket is waiting has to work the question out of the ticket
 * itself, or the question disappears and nobody answers it.
 */
export function askFromDetail(detail: EventDetail | null | undefined): AskView | null {
  if (!detail || detail.event.status !== "asking") return null;
  const identification = finalIdentification(detail.identifications);
  const posterior = posteriorCandidates(identification?.posterior);
  const candidates = (posterior.length > 0 ? posterior : (identification?.candidates ?? [])).slice(
    0,
    4,
  );
  const detailQuestion = askQuestion(identification);
  // A question with nothing to offer is still a question. The model can come back
  // sure that it does not know, and the panel then shows what it thinks it saw and
  // a box to type in, rather than disappearing and leaving the ticket stuck.
  return {
    type: "ask.opened",
    event_id: detail.event.id,
    crop_url: detail.event.crop_url ?? null,
    candidates,
    description: askDescription(identification),
    question: detailQuestion?.question ?? null,
    choices: detailQuestion?.choices ?? null,
  };
}

/**
 * What the model says it is looking at, when it says anything.
 *
 * This is the model's own words, so it is data and never anything else: it is capped
 * at 120 characters and printed as a quoted sentence. A backend older than the field
 * sends nothing and the ask reads as it always did.
 */
export function askDescription(source: unknown): string | null {
  if (!source || typeof source !== "object") return null;
  // The socket calls it looks_like and the identification read calls it
  // description. Both are the model's own sentence about the photo.
  const fields = source as { description?: unknown; looks_like?: unknown };
  const raw = typeof fields.looks_like === "string" ? fields.looks_like : fields.description;
  if (typeof raw !== "string") return null;
  const text = raw.replace(/\s+/g, " ").trim().slice(0, 120);
  return text.length > 0 ? text : null;
}

/** The same shape the socket sends, with the candidate list left as a plain array. */
export type AskView = {
  type: "ask.opened";
  event_id: number;
  crop_url: string | null;
  candidates: { label: string; p: number }[];
  /** The model's sentence about the photo, when the payload carries one. */
  description?: string | null;
  /**
   * The one question that matters, PLAN.md 21a item 40: how many gigabytes, what
   * wattage, dead or still works. When the payload carries one, it is the heading
   * and the choices are the buttons, in place of a list of labels.
   */
  question?: string | null;
  choices?: string[] | null;
};

/**
 * The detail question the model asked, read out of whatever payload carries it.
 *
 * Model text, so it is treated as data at every step: the question is collapsed to
 * single spaces and capped at 120 characters, each choice at 40, and at most four
 * are kept, which is what the panel can show. A backend that sends neither field
 * leaves both null and the ask reads as a list of labels, exactly as before.
 */
export function askQuestion(source: unknown): { question: string; choices: string[] } | null {
  if (!source || typeof source !== "object") return null;
  const raw = (source as { question?: unknown }).question;
  if (typeof raw !== "string") return null;
  const question = raw.replace(/\s+/g, " ").trim().slice(0, 120);
  if (question.length === 0) return null;
  const list = (source as { choices?: unknown }).choices;
  if (!Array.isArray(list)) return null;
  const choices = list
    .filter((c): c is string => typeof c === "string")
    .map((c) => c.replace(/\s+/g, " ").trim().slice(0, 40))
    .filter((c) => c.length > 0)
    .slice(0, 4);
  return choices.length >= 2 ? { question, choices } : null;
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
  /** True when the top two answers come out the same in the books. */
  same_treatment: boolean;
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
      expression: `The books lose ${cents((record.book_value_cents ?? 0) - (record.tax_basis_cents ?? 0))} more than the return does`,
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
    candidates: visionCandidates(identification),
    posterior: posteriorCandidates(identification?.posterior),
    same_treatment: sameTreatment(identification?.posterior),
    formula: formulaFor(detail),
    rule_ids: [...ruleIds],
    human_confirmed: byHand || (detail.corrections ?? []).length > 0,
    estimates: estimateLines(detail.item_record),
    mass_g: detail.event.mass_g ?? null,
    mass_err_g: detail.event.mass_err_g ?? null,
  };
}

/**
 * Account code to account name.
 *
 * The journal read names every account; the single event read sends the code
 * alone. Taking the names from the journal keeps one source for them, rather
 * than a second copy of the chart of accounts living in the dashboard.
 */
export function accountNames(
  entries: JournalEntryRead[] | null | undefined,
): Map<string, string> {
  const names = new Map<string, string>();
  for (const entry of entries ?? []) {
    for (const line of entry.lines ?? []) {
      if (line.account_name) names.set(line.account, line.account_name);
    }
  }
  return names;
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
 * The close names its own checks, so that name wins. The map behind it is what
 * an older close, which sent the key alone, still reads as.
 */
const CHECK_NAMES: { [k: string]: string } = {
  mass_conservation: "Mass conservation",
  ledger_balance: "Ledger balance",
  register_consistency: "Register consistency",
  unresolved_asks: "Unresolved asks",
  low_confidence_share: "Settled by a person",
};

export function checkName(check: CloseCheck): string {
  if (check.title) return check.title;
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

/**
 * A check writes its balance as padded text, which only lines up in a monospace
 * face, and the dashboard has none. The numbers are on the check as numbers, so
 * the balance is drawn from those and only the prose under it is printed.
 */
export function checkProse(check: CloseCheck): string {
  const detail = check.detail ?? "";
  const split = detail.indexOf("\n\n");
  if (split < 0) return detail.includes("\n") ? "" : detail;
  return detail.slice(split + 2).trim();
}

/**
 * The investigator writes markdown. The page is not a markdown reader, so the
 * note comes back as the lines it is made of, with the markers taken off.
 */
export type NoteBlock = { kind: "heading" | "text"; text: string };

export function noteBlocks(markdown: string | null | undefined): NoteBlock[] {
  if (!markdown) return [];
  return markdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0)
    .map((block) => {
      const heading = /^#{1,6}\s+/.test(block);
      const text = block
        .replace(/^#{1,6}\s+/, "")
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .replace(/`(.+?)`/g, "$1")
        .replace(/\s*\n\s*/g, " ")
        .trim();
      return { kind: heading ? ("heading" as const) : ("text" as const), text };
    })
    .filter((block) => block.text.length > 0);
}

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

// Trends -------------------------------------------------------------------

/**
 * The bucketing `GET /api/stats` is asked for, PLAN.md 21a items 43 and 46.
 *
 * The response itself is the contract's `StatsResponse`: a list of day or week
 * buckets, the averages, the suggestions and the paragraph. There are no totals
 * on the wire, because a total is the sum of the buckets and one arithmetic is
 * safer than two. `statsTotals` does that sum here.
 */
export type StatsRange = NonNullable<StatsResponse["bucket"]>;

/** The five buckets a person recognises, PLAN.md 21a item 43. */
export const STATS_CATEGORIES = ["food", "packaging", "equipment", "e-waste", "other"] as const;
export type StatsCategory = CategoryStat["category"];

/** The range added up, in the backend's own field names. */
export type StatsTotals = {
  tosses: number;
  wasted_cents: number;
  book_loss_cents: number;
  estimated_value_cents: number;
  kg_landfill: number;
  kg_co2e_avoided: number;
  asks: number;
};

const EMPTY_TOTALS: StatsTotals = {
  tosses: 0,
  wasted_cents: 0,
  book_loss_cents: 0,
  estimated_value_cents: 0,
  kg_landfill: 0,
  kg_co2e_avoided: 0,
  asks: 0,
};

/** Every bucket in the range, added up. A missing figure counts as nothing. */
export function statsTotals(stats: StatsResponse | null | undefined): StatsTotals {
  return (stats?.buckets ?? []).reduce<StatsTotals>(
    (sum, bucket: StatsBucket) => ({
      tosses: sum.tosses + (bucket.tosses ?? 0),
      wasted_cents: sum.wasted_cents + (bucket.wasted_cents ?? 0),
      book_loss_cents: sum.book_loss_cents + (bucket.book_loss_cents ?? 0),
      estimated_value_cents: sum.estimated_value_cents + (bucket.estimated_value_cents ?? 0),
      kg_landfill: sum.kg_landfill + (bucket.kg_landfill ?? 0),
      kg_co2e_avoided: sum.kg_co2e_avoided + (bucket.kg_co2e_avoided ?? 0),
      asks: sum.asks + (bucket.asks ?? 0),
    }),
    { ...EMPTY_TOTALS },
  );
}

/** The per day figures, with nothing where the backend sent nothing. */
export function statsAverages(stats: StatsResponse | null | undefined): StatsAverages {
  return stats?.averages ?? {};
}

/** The words for a category, so no screen spells one its own way. */
export function categoryWords(category: string): string {
  if (category === "e-waste") return "Electronics";
  if (category === "food") return "Food";
  if (category === "packaging") return "Packaging";
  if (category === "equipment") return "Equipment";
  if (category === "other") return "Other";
  return category.charAt(0).toUpperCase() + category.slice(1);
}

export type CategoryBar = {
  category: string;
  label: string;
  cents: number;
  tosses: number;
  massG: number;
  /** 0 to 1, against the largest row, for the bar's width. */
  share: number;
};

/**
 * The category rows in the order a person reads them, biggest first, each with
 * its share of the largest so a bar can be drawn by hand out of two blocks.
 *
 * Every bucket carries its own category list, so the rows are added across the
 * range first. Rows with nothing in them are left out, because a bar of zero says
 * nothing.
 */
export function categoryBars(stats: StatsResponse | null | undefined): CategoryBar[] {
  const summed = new Map<string, { cents: number; tosses: number; kg: number }>();
  for (const bucket of stats?.buckets ?? []) {
    for (const row of bucket.by_category ?? []) {
      const name = String(row.category);
      const held = summed.get(name) ?? { cents: 0, tosses: 0, kg: 0 };
      held.cents += row.cents ?? 0;
      held.tosses += row.tosses ?? 0;
      held.kg += row.kg ?? 0;
      summed.set(name, held);
    }
  }
  const rows = [...summed.entries()].filter(([, row]) => row.cents > 0 || row.tosses > 0);
  const top = rows.reduce((max, [, row]) => Math.max(max, Math.abs(row.cents)), 0);
  return rows
    .map(([name, row]) => ({
      category: name,
      label: categoryWords(name),
      cents: Math.abs(row.cents),
      tosses: row.tosses,
      massG: row.kg * 1000,
      share: top > 0 ? Math.abs(row.cents) / top : 0,
    }))
    .sort((a, b) => b.cents - a.cents || b.tosses - a.tosses);
}

/** True when the read came back but has nothing in it yet. */
export function statsEmpty(stats: StatsResponse | null | undefined): boolean {
  if (!stats) return true;
  return statsTotals(stats).tosses === 0 && categoryBars(stats).length === 0;
}
