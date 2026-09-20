"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import type { EventDetail, EventSummary, OptionScoreRead } from "@/lib/types";
import {
  bestOption,
  co2eAvoided,
  fineToBin,
  ticketFigure,
  ticketHeadline,
  ticketTone,
} from "@/lib/derive";
import { imageSrc, useAnswerAsk, useAssetTag, useSettings, useVoidEvent } from "@/lib/api";
import { classLine } from "@/lib/copy";
import {
  ESTIMATE_MARKER,
  co2eParts,
  formatMass,
  formatMassError,
  formatMoney,
  formatOption,
  formatTag,
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

/**
 * Full is the sheet on the Live page and the event page. Compact is the same
 * sheet printed small, for the tickets that came before the current one: the
 * label, the class, the mass, the figure and which option would have been best,
 * with the option table and the menu left off.
 */
export type TicketSize = "full" | "compact";

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
  size = "full",
  showMenu = true,
  children,
}: {
  event: EventSummary;
  detail?: EventDetail | null;
  phase?: TicketPhase;
  arrival?: number;
  width?: number | string;
  size?: TicketSize;
  showMenu?: boolean;
  children?: React.ReactNode;
}) {
  const record = detail?.item_record ?? null;
  const figure = ticketFigure(event, record);
  const headline = ticketHeadline(event, record, detail?.options ?? null);
  const tag = useAssetTag(record?.asset_id);
  const settings = useSettings();
  const sort = classLine(record?.class ?? event.class, tag ? formatTag(tag) : null);
  const counted = useCountUp(figure.cents, arrival, phase === "identified" && arrival > 0);
  const identified = phase === "identified" && event.label !== null;
  // The money leaves the critical path, so a ticket can be labelled seconds
  // before it is valued. Until it is, the sheet prints the mass, not a false zero.
  const shown = identified && headline.known;
  const options = detail?.options ?? [];
  const mass = event.mass_g ?? 0;
  // An open question is amber whatever the options say, because the answer is
  // not settled yet. Otherwise the ticket carries the engine's own tone.
  const asking = children != null;
  const tone = asking ? "caution" : ticketTone(options, settings.data);
  const compact = size === "compact";
  const best = bestOption(options);
  // When the bin was already the right answer there is nothing to argue about, so
  // the option table folds to the one row and says so.
  const settled = fineToBin(options, settings.data);
  // A headline the backend sent with no money in it is a sentence. Printing it at
  // 72 px would shout a line that is not a number.
  const wordsOnly = headline.kind === "given" && !headline.text;

  return (
    <article
      className={cx(
        "ticket-arrive rounded-ticket border border-rule bg-surface shadow-ticket",
        compact ? "p-3 lg:p-4" : "p-5 lg:p-6",
        // The tone band, the same 4 px edge the phone sheet carries.
        tone === "kept" && "border-t-4 border-t-kept",
        tone === "caution" && "border-t-4 border-t-caution",
        tone === "red" && "border-t-4 border-t-red-ink",
        arrival > 0 && "animate-ticket-in",
      )}
      style={{ width: width ?? "var(--ticket-w)", maxWidth: "100%" }}
      key={arrival}
    >
      <header
        className={cx(
          "flex items-start gap-3",
          // A question tints its own header, so the ticket waiting on a person is
          // the one thing on the page that is not the usual white paper.
          asking &&
            "-mx-5 -mt-5 bg-caution-tint px-5 pb-4 pt-5 lg:-mx-6 lg:-mt-6 lg:px-6 lg:pt-6",
        )}
      >
        {/* An ask shows the crop large in its own body, so the header does not repeat it. */}
        {children ? null : (
          <CropFrame
            src={imageSrc(event.crop_url)}
            label={event.label ?? "Item on the scale"}
            size={compact ? 44 : "var(--crop-ticket)"}
            className={identified ? "animate-fade-in" : undefined}
          />
        )}
        <div className="min-w-0 flex-1">
          <h2 className="text-section">{identified ? event.label : "Identifying"}</h2>
          {identified && sort ? (
            <p className="pt-1 text-caption text-ink-soft">{sort}</p>
          ) : null}
          <p className="pt-1 text-body text-ink-soft">
            <Mass grams={mass} eventId={event.id} focus="mass" />{" "}
            <span className="text-ink-soft">{formatMassError(event.mass_err_g ?? 0)}</span>
          </p>
          {compact ? null : <p className="pt-1 text-caption text-ink-soft">Ticket {event.id}</p>}
        </div>
        {compact ? (
          <span className="shrink-0 text-caption text-ink-soft">Ticket {event.id}</span>
        ) : showMenu ? (
          <TicketMenu event={event} />
        ) : null}
      </header>

      {children ? (
        <div className="pt-4">{children}</div>
      ) : (
        <>
          {/* What the toss means, in the words its class earns: wasted, written
              off, worth about, or the carbon for packaging. PLAN.md 21a item 41. */}
          <div
            className={cx("flex flex-wrap items-end gap-x-3 gap-y-1", compact ? "pt-3" : "pt-5")}
          >
            {shown && headline.lead ? (
              <span className={cx("pb-2", wordsOnly ? "text-section" : "text-body")}>
                {headline.lead}
              </span>
            ) : null}
            <span
              className={cx(
                "font-condensed leading-none empty:hidden",
                compact ? "text-total" : "text-figure",
                shown && headline.loss && "text-red-ink",
              )}
            >
              {shown
                ? headline.kind === "given"
                  ? headline.text
                  : headline.kind === "carbon"
                    ? co2eParts(headline.kg).value
                    : formatMoney(Math.abs(counted), { symbol: true })
                : formatMass(mass)}
            </span>
            <span className="pb-2 text-body text-ink-soft">
              {shown ? (
                headline.trail ? (
                  <Term>{headline.trail}</Term>
                ) : null
              ) : identified ? (
                "on the scale, being valued"
              ) : (
                "on the scale"
              )}
              {shown && headline.estimate ? (
                <span className="pl-1">{ESTIMATE_MARKER}</span>
              ) : null}
            </span>
          </div>

          {compact ? (
            best ? (
              <p className="pt-2 text-caption text-ink-soft">
                Best was {formatOption(best.option).toLowerCase()}, at{" "}
                {formatMoney(best.net_after_tax_cents, { symbol: true })} after tax.
              </p>
            ) : null
          ) : identified && options.length > 0 ? (
            <OptionTable eventId={event.id} options={options} settled={settled} />
          ) : (
            <p className="pt-4 text-caption text-ink-soft">
              {!identified
                ? "The mass is in. The label and the options land next."
                : !shown
                  ? "The label is in. The money and the options land next."
                  : "No options were scored for this one."}
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
  settled = false,
}: {
  eventId: number;
  options: OptionScoreRead[];
  /**
   * True when the bin was already the right answer. The table then prints the one
   * row that settled it and says "Fine to bin", with the rest a click away, so a
   * ticket nobody has to act on does not read like four choices to weigh up.
   */
  settled?: boolean;
}) {
  const best = bestOption(options);
  const [expanded, setExpanded] = useState(false);
  const collapsed = settled && !expanded;
  const shown = collapsed && best ? [best] : options;
  return (
    <section className="pt-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h3 className="text-section">{settled ? "Fine to bin" : "What you could have done"}</h3>
        {settled ? (
          <button
            type="button"
            onClick={() => setExpanded((on) => !on)}
            className="text-caption text-ink-soft underline underline-offset-2"
          >
            {expanded ? "Hide the other options" : `Show all ${options.length} options`}
          </button>
        ) : null}
      </div>
      {collapsed ? (
        <p className="pt-1 text-caption text-ink-soft">
          Nothing else was worth the trouble, so the bin was the right answer.
        </p>
      ) : null}
      <div className="mt-2 overflow-x-auto">
        <table className="ledger w-full min-w-[240px] border-collapse text-body sm:min-w-[320px]">
          <thead>
            <tr className="border-b border-rule bg-bar text-caption text-ink-soft">
              <th className="py-1 font-normal">Option</th>
              <th className="py-1 text-right font-normal">After tax ($)</th>
              <th className="py-1 text-right font-normal">CO2e avoided (kg)</th>
              {/* Four columns do not fit beside the rail on a phone, and the
                  landfill grams are the one a person acts on least. */}
              <th className="hidden py-1 text-right font-normal sm:table-cell">Landfill (g)</th>
            </tr>
          </thead>
          <tbody className="animate-fade-in">
            {shown.map((option) => {
              const isBest = best?.option === option.option;
              return (
                <tr
                  key={option.option}
                  className={cx(
                    "border-b border-rule",
                    option.allowed ? "h-row" : "align-top",
                    isBest && "border-l-2 border-l-kept bg-kept-tint",
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
                      kg={co2eAvoided(option)}
                      eventId={eventId}
                      focus={`${option.option} carbon`}
                      unit={false}
                    />
                  </td>
                  <td className="hidden text-right sm:table-cell">
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
