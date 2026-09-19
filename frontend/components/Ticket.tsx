"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import type { EventDetail, OptionScore } from "@/lib/types";
import {
  ESTIMATE_MARKER,
  formatMass,
  formatMassError,
  formatMoney,
  isNegativeCents,
} from "@/lib/format";
import { Co2, Mass, Money } from "./Figure";
import { CropFrame } from "./CropFrame";
import { cx } from "./ui";

// The central object of the interface. It prints on Live, in the tape, on the event
// page and on the phone. The phone page copies this markup by hand, so keep the
// structure flat and the class names readable.

export type TicketPhase = "weighing" | "identified";

const OPTION_WORDS: Record<OptionScore["option"], string> = {
  trash: "Trash",
  recycle: "Recycle",
  repair: "Repair",
  resell: "Resell",
  donate: "Donate",
};

export function ticketFigure(detail: EventDetail): {
  cents: number;
  caption: string;
  estimate: boolean;
} {
  const cents = detail.event.book_amount_cents ?? 0;
  const estimate = detail.event.is_estimate;
  if (detail.event.item_class === "fixed_asset") {
    return { cents, caption: "book loss", estimate };
  }
  if (detail.event.item_class === "inventory") {
    return { cents, caption: "waste expense", estimate };
  }
  return { cents, caption: "resale value", estimate };
}

function useCountUp(target: number, arrival: number, enabled: boolean): number {
  const [value, setValue] = useState(target);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!enabled || reduced) {
      setValue(target);
      return;
    }
    const start = performance.now();
    const from = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / 400, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) frame.current = requestAnimationFrame(step);
    };
    frame.current = requestAnimationFrame(step);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [target, arrival, enabled]);

  return value;
}

export function Ticket({
  detail,
  phase = "identified",
  arrival = 0,
  width = 560,
  showMenu = true,
  children,
}: {
  detail: EventDetail;
  phase?: TicketPhase;
  arrival?: number;
  width?: number;
  showMenu?: boolean;
  children?: React.ReactNode;
}) {
  const figure = ticketFigure(detail);
  const counted = useCountUp(figure.cents, arrival, phase === "identified" && arrival > 0);
  const identified = phase === "identified";

  return (
    <article
      className={cx(
        "ticket-arrive rounded-ticket border border-rule bg-surface p-5 shadow-ticket",
        arrival > 0 && "animate-ticket-in",
      )}
      style={{ width, maxWidth: "100%" }}
      key={arrival}
    >
      <header className="flex items-start gap-3">
        <CropFrame
          src={detail.evidence?.crop ?? null}
          label={detail.event.label ?? "Item on the scale"}
          size={72}
          className={identified ? "animate-fade-in" : undefined}
        />
        <div className="flex-1">
          <h2 className="text-section">
            {identified ? (detail.event.label ?? "Unnamed item") : "Identifying"}
          </h2>
          <p className="pt-1 text-body text-ink-soft">
            <Mass grams={detail.event.mass_g} eventId={detail.event.id} focus="mass" />{" "}
            <span className="text-ink-soft">{formatMassError(detail.event.mass_err_g)}</span>
          </p>
          <p className="pt-1 text-caption text-ink-soft">Ticket {detail.event.id}</p>
        </div>
        {showMenu ? <TicketMenu eventId={detail.event.id} /> : null}
      </header>

      {children ? (
        <div className="pt-4">{children}</div>
      ) : (
        <>
          <div className="flex items-end gap-3 pt-5">
            <span
              className={cx(
                "font-condensed text-figure leading-none",
                isNegativeCents(figure.cents) && "text-red-ink",
              )}
            >
              {identified
                ? formatMoney(counted, { symbol: true })
                : formatMass(detail.event.mass_g)}
            </span>
            <span className="pb-2 text-body text-ink-soft">
              {identified ? figure.caption : "on the scale"}
              {identified && figure.estimate ? (
                <span className="pl-1">{ESTIMATE_MARKER}</span>
              ) : null}
            </span>
          </div>

          {identified && detail.options.length > 0 ? (
            <OptionTable detail={detail} />
          ) : (
            <p className="pt-4 text-caption text-ink-soft">
              The mass is in. The label and the options land next.
            </p>
          )}
        </>
      )}
    </article>
  );
}

function TicketMenu({ eventId }: { eventId: number }) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        className="rounded-control border border-control-border bg-surface p-1 text-ink-soft hover:bg-bar"
        aria-label="More actions for this ticket"
      >
        <MoreHorizontal size={16} strokeWidth={1.5} />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="min-w-[180px] rounded-control border border-control-border bg-surface p-1 text-body shadow-overlay"
        >
          <DropdownMenu.Item className="cursor-pointer rounded-control px-2 py-1 outline-none data-[highlighted]:bg-bar">
            Correct label
          </DropdownMenu.Item>
          <DropdownMenu.Item className="cursor-pointer rounded-control px-2 py-1 text-red-ink outline-none data-[highlighted]:bg-bar">
            Void ticket
          </DropdownMenu.Item>
          <DropdownMenu.Separator className="my-1 h-px bg-rule" />
          <DropdownMenu.Item asChild>
            <Link
              href={`/events/${eventId}`}
              className="block cursor-pointer rounded-control px-2 py-1 outline-none data-[highlighted]:bg-bar"
            >
              Open full detail
            </Link>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

export function OptionTable({ detail }: { detail: EventDetail }) {
  const best = detail.options.find((o) => o.allowed && o.rank === 1);
  return (
    <section className="pt-5">
      <h3 className="text-section">What you could have done</h3>
      <div className="mt-2 overflow-x-auto">
      <table className="ledger w-full min-w-[320px] border-collapse text-body">
        <thead>
          <tr className="border-b border-rule bg-bar text-caption text-ink-soft">
            <th className="py-1 font-normal">Option</th>
            <th className="py-1 text-right font-normal">After tax ($)</th>
            <th className="py-1 text-right font-normal">CO2e (kg)</th>
            <th className="py-1 text-right font-normal">Landfill (g)</th>
          </tr>
        </thead>
        <tbody className="animate-fade-in">
          {detail.options.map((option) => {
            const isBest = best?.option === option.option;
            return (
              <tr
                key={option.option}
                className={cx(
                  "h-row border-b border-rule",
                  isBest && "border-l-2 border-l-kept",
                  !option.allowed && "text-red-ink",
                )}
              >
                <td className={cx(!option.allowed && "line-through")}>
                  {OPTION_WORDS[option.option]}
                  {isBest ? <span className="pl-2 text-caption text-kept">best</span> : null}
                  {option.needs_human_review ? (
                    <span className="pl-2 text-caption text-caution">review</span>
                  ) : null}
                </td>
                <td className="text-right">
                  {option.allowed ? (
                    <Money
                      cents={option.net_after_tax_cents}
                      eventId={detail.event.id}
                      focus={`${option.option} after tax`}
                    />
                  ) : (
                    <span className="text-caption">{option.blocked_reason}</span>
                  )}
                </td>
                <td className="text-right">
                  <Co2
                    kg={option.kg_co2e}
                    eventId={detail.event.id}
                    focus={`${option.option} carbon`}
                    unit={false}
                  />
                </td>
                <td className="text-right">
                  <Mass
                    grams={option.kg_landfill * 1000}
                    eventId={detail.event.id}
                    focus={`${option.option} landfill`}
                    unit={false}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </section>
  );
}
