"use client";

import { API_URL, useEventDetails, useSummary } from "@/lib/api";
import { askFromDetail, type AskView } from "@/lib/derive";
import { useLive, useReach } from "@/lib/live";
import { formatCount, formatMoney, formatPercent, massParts } from "@/lib/format";
import { AskPanel } from "@/components/AskPanel";
import { FirstRun } from "@/components/FirstRun";
import { ScaleStrip } from "@/components/ScaleStrip";
import { Tape } from "@/components/Tape";
import { Ticket } from "@/components/Ticket";
import {
  EmptyState,
  ErrorState,
  FinanceFooter,
  SectionTitle,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";

const TAPE_ROWS = 25;

export default function LivePage() {
  const summary = useSummary();
  const live = useLive();
  const tape = live.tape.slice(0, TAPE_ROWS);
  const details = useEventDetails(tape);
  // A question outranks the next toss. While one is open it holds the ticket, so a
  // toss landing seven seconds later cannot carry an unanswered ask off the screen.
  const waiting = tape.find((e) => e.status === "asking") ?? null;
  const open = live.ask;
  const ask: AskView | null =
    open && tape.some((e) => e.id === open.event_id)
      ? { ...open, type: "ask.opened", crop_url: open.crop_url ?? null }
      : askFromDetail(waiting ? details.get(waiting.id) : null);
  const asked = ask ? (tape.find((e) => e.id === ask.event_id) ?? null) : null;
  const ticket = asked
    ? { event: asked, phase: "weighing" as const, arrival: 0 }
    : live.ticket;
  const ticketDetail = ticket ? (details.get(ticket.event.id) ?? null) : null;
  const totals = summary.data;
  const reach = useReach(live.status, summary.isError, totals != null);

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Totals">
        {reach === "dead" ? (
          <ErrorState
            title={`Nothing is answering at ${API_URL}. The bin's service may not be running.`}
            onRetry={() => summary.refetch()}
          />
        ) : (
          <div className="grid grid-cols-2 gap-x-8 gap-y-4 border-b border-rule pb-4 sm:grid-cols-4">
            <Total
              tone="kept"
              label="Saved if followed"
              value={
                totals ? formatMoney(totals.saved_if_followed_cents ?? 0, { symbol: true }) : null
              }
            />
            <Total
              tone="kept"
              label="Kept from landfill"
              value={totals ? massParts((totals.kg_diverted ?? 0) * 1000).value : null}
              unit={totals ? massParts((totals.kg_diverted ?? 0) * 1000).unit : ""}
            />
            <Total label="Tosses" value={totals ? formatCount(totals.events ?? 0) : null} />
            <Total
              label="Right first try"
              value={
                totals
                  ? totals.first_try_accuracy === null ||
                    totals.first_try_accuracy === undefined
                    ? "None scored yet"
                    : formatPercent(totals.first_try_accuracy)
                  : null
              }
              quiet={totals ? totals.first_try_accuracy === null : false}
            />
          </div>
        )}
      </section>

      <ScaleStrip
        samples={live.samples}
        steps={live.steps}
        weight_g={live.weight_g}
        connected={live.bin.connected}
        reach={reach}
        detail={live.bin.detail}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[var(--ticket-w)_minmax(0,1fr)]">
        <section aria-label="Current ticket">
          {reach === "connecting" ? (
            <div className="flex w-ticket max-w-full flex-col gap-3 border border-rule bg-surface p-5">
              <Skeleton className="h-[var(--crop-ticket)] w-[var(--crop-ticket)]" />
              <Skeleton className="h-14 w-48" />
              <Skeleton className="h-row w-full" />
              <Skeleton className="h-row w-full" />
              <Skeleton className="h-row w-full" />
            </div>
          ) : reach === "dead" ? (
            <EmptyState title="Tickets appear here as soon as the service answers." />
          ) : ticket ? (
            <Ticket
              event={ticket.event}
              detail={ticketDetail}
              phase={ticket.phase}
              arrival={ticket.arrival}
            >
              {asked && ask ? <AskPanel ask={ask} /> : undefined}
            </Ticket>
          ) : (
            <FirstRun />
          )}
        </section>

        <section aria-label="Tape" className="min-w-0">
          <SectionTitle
            right={
              <span className="hidden text-caption text-ink-soft sm:inline">
                j and k move, Enter opens, e shows the evidence
              </span>
            }
          >
            Tape
          </SectionTitle>
          <div className="pt-2">
            {reach === "connecting" ? (
              <div className="flex flex-col gap-2">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-row w-full" />
                ))}
              </div>
            ) : reach === "dead" ? (
              <EmptyState title="The tape is whatever the service has recorded, so it is blank until it answers." />
            ) : (
              <Tape events={tape} details={details} />
            )}
          </div>
        </section>
      </div>

      <FinanceFooter />
    </div>
  );
}

function Total({
  label,
  value,
  unit,
  quiet = false,
  tone,
}: {
  label: string;
  value: string | null;
  unit?: string;
  quiet?: boolean;
  /** Set on the two totals that are money and mass kept out of the bin. */
  tone?: "kept";
}) {
  return (
    <div>
      <p className="flex items-center gap-2 text-caption text-ink-soft">
        {tone ? <StatusDot tone={tone} /> : null}
        {label}
      </p>
      {value === null ? (
        <Skeleton className="mt-1 h-7 w-24" />
      ) : quiet ? (
        <p className="pt-2 text-body text-ink-soft">{value}</p>
      ) : (
        <p className={cx("font-condensed text-total")}>
          {value}
          {unit ? <span className="pl-1 text-body text-ink-soft">{unit}</span> : null}
        </p>
      )}
    </div>
  );
}
