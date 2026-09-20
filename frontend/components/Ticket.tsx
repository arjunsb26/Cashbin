"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import type { EventDetail, EventSummary, OptionScoreRead } from "@/lib/types";
import { bestOption, ticketFigure } from "@/lib/derive";
import { imageSrc, useAnswerAsk, useAssetTag, useVoidEvent } from "@/lib/api";
import { classLine } from "@/lib/copy";
import {
  ESTIMATE_MARKER,
  formatMass,
  formatMassError,
  formatMoney,
  formatOption,
  formatTag,
  isNegativeCents,
  readLabel,
} from "@/lib/format";
import { Co2, Mass, Money } from "./Figure";
import { Term } from "./Term";
import { CropFrame } from "./CropFrame";
import { Button, Field, Input, cx } from "./ui";

// The central object of the interface. It prints on Live, in the tape, on the event
// page and on the phone. The phone page copies this markup by hand, so keep the
// structure flat and the class names readable.

export type TicketPhase = "weighing" | "identified";

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
  event,
  detail,
  phase = "identified",
  arrival = 0,
  width,
  showMenu = true,
  children,
}: {
  event: EventSummary;
  detail?: EventDetail | null;
  phase?: TicketPhase;
  arrival?: number;
  width?: number | string;
  showMenu?: boolean;
  children?: React.ReactNode;
}) {
  const record = detail?.item_record ?? null;
  const figure = ticketFigure(event, record);
  const tag = useAssetTag(record?.asset_id);
  const sort = classLine(record?.class ?? event.class, tag ? formatTag(tag) : null);
  const counted = useCountUp(figure.cents, arrival, phase === "identified" && arrival > 0);
  const identified = phase === "identified" && event.label !== null;
  const options = detail?.options ?? [];
  const mass = event.mass_g ?? 0;

  return (
    <article
      className={cx(
        "ticket-arrive rounded-ticket border border-rule bg-surface p-5 shadow-ticket lg:p-6",
        arrival > 0 && "animate-ticket-in",
      )}
      style={{ width: width ?? "var(--ticket-w)", maxWidth: "100%" }}
      key={arrival}
    >
      <header className="flex items-start gap-3">
        {/* An ask shows the crop large in its own body, so the header does not repeat it. */}
        {children ? null : (
          <CropFrame
            src={imageSrc(event.crop_url)}
            label={event.label ?? "Item on the scale"}
            size="var(--crop-ticket)"
            className={identified ? "animate-fade-in" : undefined}
          />
        )}
        <div className="flex-1">
          <h2 className="text-section">{identified ? event.label : "Identifying"}</h2>
          {identified && sort ? (
            <p className="pt-1 text-caption text-ink-soft">{sort}</p>
          ) : null}
          <p className="pt-1 text-body text-ink-soft">
            <Mass grams={mass} eventId={event.id} focus="mass" />{" "}
            <span className="text-ink-soft">{formatMassError(event.mass_err_g ?? 0)}</span>
          </p>
          <p className="pt-1 text-caption text-ink-soft">Ticket {event.id}</p>
        </div>
        {showMenu ? <TicketMenu event={event} /> : null}
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
              {identified ? formatMoney(counted, { symbol: true }) : formatMass(mass)}
            </span>
            <span className="pb-2 text-body text-ink-soft">
              {identified ? <Term>{figure.caption}</Term> : "on the scale"}
              {identified && figure.estimate ? (
                <span className="pl-1">{ESTIMATE_MARKER}</span>
              ) : null}
            </span>
          </div>

          {identified && options.length > 0 ? (
            <OptionTable eventId={event.id} options={options} />
          ) : (
            <p className="pt-4 text-caption text-ink-soft">
              {identified
                ? "No options were scored for this one."
                : "The mass is in. The label and the options land next."}
            </p>
          )}
        </>
      )}
    </article>
  );
}

function TicketMenu({ event }: { event: EventSummary }) {
  const [correcting, setCorrecting] = useState(false);
  const voidEvent = useVoidEvent();

  return (
    <>
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
            <DropdownMenu.Item
              className="cursor-pointer rounded-control px-2 py-1 outline-none data-[highlighted]:bg-bar"
              onSelect={() => setCorrecting(true)}
            >
              Correct label
            </DropdownMenu.Item>
            <DropdownMenu.Item
              className="cursor-pointer rounded-control px-2 py-1 text-red-ink outline-none data-[highlighted]:bg-bar"
              onSelect={() => voidEvent.mutate(event.id)}
              disabled={event.status === "void"}
            >
              Void ticket
            </DropdownMenu.Item>
            <DropdownMenu.Separator className="my-1 h-px bg-rule" />
            <DropdownMenu.Item asChild>
              <Link
                href={`/events/${event.id}`}
                className="block cursor-pointer rounded-control px-2 py-1 outline-none data-[highlighted]:bg-bar"
              >
                Open full detail
              </Link>
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <CorrectLabelDialog
        eventId={event.id}
        current={event.label ?? null}
        open={correcting}
        onOpenChange={setCorrecting}
      />
    </>
  );
}

/**
 * What a person types is read into a small object before it goes anywhere, and the
 * dialog says what it understood and what it left out.
 */
function CorrectLabelDialog({
  eventId,
  current,
  open,
  onOpenChange,
}: {
  eventId: number;
  current: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [raw, setRaw] = useState("");
  const answer = useAnswerAsk();
  const read = readLabel(raw);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setRaw("");
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 w-[420px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 rounded-control border border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
        >
          <Dialog.Title className="text-title">Correct the label</Dialog.Title>
          <p className="pb-4 pt-1 text-caption text-ink-soft">
            {current ? `Ticket ${eventId} is recorded as ${current}.` : `Ticket ${eventId}.`} The
            correction is remembered, so the next one like it is recognised.
          </p>
          <Field
            label="What it really is"
            hint="Up to 40 characters. Letters, digits, spaces and hyphens."
            htmlFor={`correct-${eventId}`}
          >
            <Input
              id={`correct-${eventId}`}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              placeholder="usb-c charger"
            />
          </Field>
          {raw.length > 0 ? (
            <p className={cx("pt-2 text-caption", read.ok ? "text-ink-soft" : "text-red-ink")}>
              {read.ok
                ? `Understood as "${read.label}".`
                : "Nothing usable in that. Try letters and digits."}
              {read.dropped ? ` Left out: ${read.dropped}` : ""}
            </p>
          ) : null}
          <div className="flex justify-end gap-2 pt-5">
            <Dialog.Close asChild>
              <Button>Cancel</Button>
            </Dialog.Close>
            <Button
              tone="primary"
              disabled={!read.ok}
              loading={answer.isPending}
              onClick={() =>
                answer.mutate(
                  { event_id: eventId, label: read.label, by: "person" },
                  { onSuccess: () => onOpenChange(false) },
                )
              }
            >
              Save the label
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function OptionTable({
  eventId,
  options,
}: {
  eventId: number;
  options: OptionScoreRead[];
}) {
  const best = bestOption(options);
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
            {options.map((option) => {
              const isBest = best?.option === option.option;
              return (
                <tr
                  key={option.option}
                  className={cx(
                    "border-b border-rule",
                    option.allowed ? "h-row" : "align-top",
                    isBest && "border-l-2 border-l-kept",
                    !option.allowed && "text-red-ink",
                  )}
                >
                  <td>
                    <span className={cx(!option.allowed && "line-through")}>
                      {formatOption(option.option)}
                    </span>
                    {isBest ? <span className="pl-2 text-caption text-kept">best</span> : null}
                    {option.needs_human_review ? (
                      <span className="pl-2 text-caption text-caution">review</span>
                    ) : null}
                    {!option.allowed && option.blocked_reason ? (
                      <span className="block text-caption">{option.blocked_reason}</span>
                    ) : null}
                  </td>
                  <td className={cx("text-right", !option.allowed && "line-through")}>
                    <Money
                      cents={option.net_after_tax_cents}
                      eventId={eventId}
                      focus={`${option.option} after tax`}
                    />
                  </td>
                  <td className="text-right">
                    <Co2
                      kg={option.kg_co2e ?? null}
                      eventId={eventId}
                      focus={`${option.option} carbon`}
                      unit={false}
                    />
                  </td>
                  <td className="text-right">
                    <Mass
                      grams={(option.kg_landfill ?? 0) * 1000}
                      eventId={eventId}
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
