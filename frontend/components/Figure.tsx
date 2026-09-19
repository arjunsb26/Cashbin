"use client";

import type { ReactNode } from "react";
import { useEvidence } from "./Providers";
import { cx } from "./ui";
import {
  ESTIMATE_MARKER,
  co2eParts,
  formatMoney,
  isNegativeCents,
  massParts,
} from "@/lib/format";

/**
 * Every money, mass and carbon figure goes through here, so every one of them
 * opens the evidence drawer and carries the same numerals.
 */
function Clickable({
  eventId,
  focus,
  className,
  children,
  title,
}: {
  eventId: number | null | undefined;
  focus: string;
  className?: string;
  children: ReactNode;
  title: string;
}) {
  const evidence = useEvidence();
  if (eventId === null || eventId === undefined) {
    return <span className={className}>{children}</span>;
  }
  return (
    <button
      type="button"
      className={cx("evidence-figure text-left", className)}
      onClick={() => evidence.open(eventId, focus)}
      aria-label={`${title}. Open the evidence for ticket ${eventId}.`}
    >
      {children}
    </button>
  );
}

export function Money({
  cents,
  symbol = false,
  eventId,
  focus = "money",
  estimate = false,
  className,
}: {
  cents: number;
  symbol?: boolean;
  eventId?: number | null;
  focus?: string;
  estimate?: boolean;
  className?: string;
}) {
  const negative = isNegativeCents(cents);
  return (
    <Clickable
      eventId={eventId}
      focus={focus}
      title={formatMoney(cents, { symbol: true })}
      className={cx(negative && "text-red-ink", className)}
    >
      {estimate ? <span className="pr-1 text-caption text-ink-soft">{ESTIMATE_MARKER}</span> : null}
      {formatMoney(cents, { symbol })}
    </Clickable>
  );
}

export function Mass({
  grams,
  eventId,
  focus = "mass",
  className,
  unit = true,
}: {
  grams: number;
  eventId?: number | null;
  focus?: string;
  className?: string;
  /** Off inside a table, where the unit is named once in the column header. */
  unit?: boolean;
}) {
  const parts = massParts(grams);
  return (
    <Clickable
      eventId={eventId}
      focus={focus}
      title={`${parts.value} ${parts.unit}`}
      className={className}
    >
      {parts.value}
      {unit ? <span className="pl-[2px] text-ink-soft">{parts.unit}</span> : null}
    </Clickable>
  );
}

export function Co2({
  kg,
  eventId,
  focus = "carbon",
  className,
  unit = true,
}: {
  kg: number | null;
  eventId?: number | null;
  focus?: string;
  className?: string;
  /** Off inside a table, where the unit is named once in the column header. */
  unit?: boolean;
}) {
  const parts = co2eParts(kg);
  return (
    <Clickable
      eventId={eventId}
      focus={focus}
      title={`${parts.value} ${parts.unit}`}
      className={className}
    >
      {parts.value}
      {unit && parts.unit ? (
        <span className="pl-[2px] text-ink-soft">{parts.unit}</span>
      ) : null}
    </Clickable>
  );
}

export function EstimateMark() {
  return <span className="pl-1 text-caption text-ink-soft">{ESTIMATE_MARKER}</span>;
}
