"use client";

import { useSummary } from "@/lib/api";
import { useLive } from "@/lib/live";
import { formatCount, formatMoney, formatPercent, massParts } from "@/lib/format";
import { AskPanel } from "@/components/AskPanel";
import { ScaleStrip } from "@/components/ScaleStrip";
import { Tape } from "@/components/Tape";
import { Ticket } from "@/components/Ticket";
import {
  EmptyState,
  ErrorState,
  FinanceFooter,
  SectionTitle,
  Skeleton,
  cx,
} from "@/components/ui";

export default function LivePage() {
  const summary = useSummary();
  const live = useLive();
  const ticket = live.ticket;

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Totals">
        {summary.isError ? (
          <ErrorState
            title="The totals did not load. The backend is not answering."
            onRetry={() => summary.refetch()}
          />
        ) : (
          <div className="grid grid-cols-2 gap-x-8 gap-y-4 border-b border-rule pb-4 sm:grid-cols-4">
            <Total
              label="Saved if followed"
              value={
                summary.data ? formatMoney(summary.data.saved_if_followed_cents, { symbol: true }) : null
              }
            />
            <Total
              label="Kept from landfill"
              value={summary.data ? massParts(summary.data.kg_diverted * 1000).value : null}
              unit={summary.data ? massParts(summary.data.kg_diverted * 1000).unit : ""}
            />
            <Total label="Tosses" value={summary.data ? formatCount(summary.data.n_events) : null} />
            <Total
              label="Right first try"
              value={summary.data ? formatPercent(summary.data.first_try_accuracy) : null}
            />
          </div>
        )}
      </section>

      <ScaleStrip
        samples={live.samples}
        steps={live.steps}
        weight_g={live.weight_g}
        connected={live.device.bin === "connected"}
        connecting={live.status === "connecting"}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[560px_minmax(0,1fr)]">
        <section aria-label="Current ticket">
          {live.status === "connecting" ? (
            <div className="flex w-ticket max-w-full flex-col gap-3 border border-rule bg-surface p-5">
              <Skeleton className="h-[72px] w-[72px]" />
              <Skeleton className="h-14 w-48" />
              <Skeleton className="h-row w-full" />
              <Skeleton className="h-row w-full" />
              <Skeleton className="h-row w-full" />
            </div>
          ) : ticket ? (
            <Ticket detail={ticket.detail} phase={ticket.phase} arrival={ticket.arrival}>
              {live.ask ? <AskPanel ask={live.ask} /> : undefined}
            </Ticket>
          ) : (
            <EmptyState title="No ticket on the scale. Toss something in the bin, or run the simulator." />
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
            {live.status === "connecting" ? (
              <div className="flex flex-col gap-2">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-row w-full" />
                ))}
              </div>
            ) : (
              <Tape events={live.tape} />
            )}
          </div>
        </section>
      </div>

      <FinanceFooter />
    </div>
  );
}

function Total({ label, value, unit }: { label: string; value: string | null; unit?: string }) {
  return (
    <div>
      <p className="text-caption text-ink-soft">{label}</p>
      {value === null ? (
        <Skeleton className="mt-1 h-7 w-24" />
      ) : (
        <p className={cx("font-condensed text-total")}>
          {value}
          {unit ? <span className="pl-1 text-body text-ink-soft">{unit}</span> : null}
        </p>
      )}
    </div>
  );
}
