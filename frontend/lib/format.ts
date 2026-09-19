// Every number the user sees is formatted here, so the dashboard, the kit and the
// phone copy cannot drift. Accounting rules come from DESIGN.md section 2.

const THIN_SPACE = " ";

export const ESTIMATE_MARKER = "est.";
export const FINANCE_FOOTER = "Estimates for review. Not tax advice.";

const money = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const oneDecimal = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const twoDecimal = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const whole = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

export type MoneyOptions = {
  /** Show the currency symbol. Tables show it on the header and total rows only. */
  symbol?: boolean;
};

/**
 * Accounting money from integer cents. Negatives come back in parentheses.
 * The caller colours a negative in red-ink; isNegativeCents says when.
 */
export function formatMoney(cents: number, options: MoneyOptions = {}): string {
  const magnitude = money.format(Math.abs(cents) / 100);
  const withSymbol = options.symbol ? `$${magnitude}` : magnitude;
  return cents < 0 ? `(${withSymbol})` : withSymbol;
}

export function isNegativeCents(cents: number): boolean {
  return cents < 0;
}

/** Signed form for places that read as a delta, for example the LCD and the header. */
export function formatSignedMoney(cents: number): string {
  const magnitude = money.format(Math.abs(cents) / 100);
  return cents < 0 ? `-$${magnitude}` : `$${magnitude}`;
}

export type NumberWithUnit = { value: string; unit: string };

/** Mass in grams below a kilogram, kilograms above it. The unit is set in ink-soft. */
export function massParts(grams: number): NumberWithUnit {
  if (Math.abs(grams) >= 1000) {
    return { value: oneDecimal.format(grams / 1000), unit: "kg" };
  }
  if (Math.abs(grams) < 10 && grams !== 0 && !Number.isInteger(grams)) {
    return { value: oneDecimal.format(grams), unit: "g" };
  }
  return { value: whole.format(grams), unit: "g" };
}

export function formatMass(grams: number): string {
  const parts = massParts(grams);
  return `${parts.value}${THIN_SPACE}${parts.unit}`;
}

/** Mass error prints beside the mass on the ticket, for example 212 g +/- 2. */
export function formatMassError(grams: number): string {
  return `+/-${THIN_SPACE}${whole.format(Math.abs(grams))}`;
}

export function kgParts(kg: number | null): NumberWithUnit {
  if (kg === null) return { value: "unknown", unit: "" };
  return { value: twoDecimal.format(kg), unit: "kg" };
}

export function co2eParts(kg: number | null): NumberWithUnit {
  if (kg === null) return { value: "unknown", unit: "" };
  return { value: twoDecimal.format(kg), unit: "kg CO2e" };
}

export function formatCo2e(kg: number | null): string {
  const parts = co2eParts(kg);
  return parts.unit ? `${parts.value}${THIN_SPACE}${parts.unit}` : parts.value;
}

/** Takes a fraction, prints whole percent. 0.89 reads 89%. */
export function formatPercent(fraction: number, decimals = 0): string {
  const formatter = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `${formatter.format(fraction * 100)}%`;
}

export function formatCount(n: number): string {
  return whole.format(n);
}

/** Model cost per event, held in millionths of a dollar. */
export function formatMicroUsd(microUsd: number): string {
  if (microUsd === 0) return "0.00";
  const cents = microUsd / 10000;
  return `${money.format(cents / 100)}`;
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(d);
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

/** Percentage points, used by the option table and the learning chart. */
export function formatProbability(p: number): string {
  return formatPercent(p, 0);
}

/**
 * Free text typed by a person is never passed along as written.
 * Same rule as the backend: trimmed, max 40 characters, letters digits spaces
 * and hyphens only, lowercased. Returns what was understood and what was dropped.
 */
export type ReadLabel = {
  ok: boolean;
  label: string;
  dropped: string | null;
};

const ALLOWED = /[^a-z0-9 -]+/g;

export function readLabel(raw: string): ReadLabel {
  const lowered = raw.normalize("NFKC").toLowerCase();
  const stripped = lowered.replace(ALLOWED, " ");
  const collapsed = stripped.replace(/\s+/g, " ").trim();
  const capped = collapsed.slice(0, 40);
  const droppedChars = lowered.replace(/[a-z0-9 -]+/g, "").length > 0;
  const droppedLength = collapsed.length > 40;
  let dropped: string | null = null;
  if (droppedChars && droppedLength) {
    dropped = "Characters we do not accept, and everything past 40 characters.";
  } else if (droppedChars) {
    dropped = "Characters we do not accept.";
  } else if (droppedLength) {
    dropped = "Everything past 40 characters.";
  }
  return { ok: capped.length > 0, label: capped, dropped };
}
