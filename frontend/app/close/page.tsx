"use client";

import Link from "next/link";
import { useClose, useEvents, useRunClose } from "@/lib/api";
import {
  checkName,
  checkNumbers,
  checkProse,
  closeReport,
  noteBlocks,
  type CheckNumber,
  type CloseReport,
} from "@/lib/derive";
import {
  formatCount,
  formatDate,
  formatGrams,
  formatMass,
  formatMoney,
  formatOption,
  formatPercent,
  formatTag,
} from "@/lib/format";
import type { CloseCheck, CloseRead } from "@/lib/types";
import { blocksOf } from "@/lib/cfo";
import { CloseMemo, Form4797, Reconciliation, Rollforward } from "@/components/CloseBlocks";
import { Co2, Mass, Money } from "@/components/Figure";
import {
  Button,
  EmptyState,
  ErrorState,
  FinanceFooter,
  PageHeader,
  SectionTitle,
  Skeleton,
  StatusDot,
  cx,
} from "@/components/ui";

/** The day in UTC, which is the clock every timestamp in the system is written on. */
function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function ClosePage() {
  const close = useClose();
  const events = useEvents();
  const run = useRunClose();

  // The period is what the tickets cover, so the statement says a real span
  // rather than a guess. With no tickets yet, it is today.
  const days = (events.data ?? [])
    .map((e) => e.created_at.slice(0, 10))
    .filter((d) => d.length === 10)
    .sort();
  const period = {
    period_start: days[0] ?? today(),
    period_end: days[days.length - 1] ?? today(),
  };

  const report = close.data ? closeReport(close.data) : null;

  return (
    <div className="max-w-[860px]">
      <PageHeader
        title="Close"
        right={
          <Button tone="primary" loading={run.isPending} onClick={() => run.mutate(period)}>
            Run close
          </Button>
        }
      />

      {close.isPending ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {close.isError ? (
        <ErrorState
          title="The close did not load. The backend is not answering."
          onRetry={() => close.refetch()}
        />
      ) : null}

      {run.isError ? (
        <ErrorState title="The close did not run. The backend is not answering." />
      ) : null}

      {close.data === null && !close.isPending ? (
        <EmptyState
          title="No close yet for this period. Run one when the round is over."
          action={
            <Button tone="primary" loading={run.isPending} onClick={() => run.mutate(period)}>
              Run close
            </Button>
          }
        />
      ) : null}

      {report ? <Statement report={report} read={close.data as CloseRead} /> : null}

      <FinanceFooter />
    </div>
  );
}

function Statement({ report, read }: { report: CloseReport; read: CloseRead }) {
  const green = report.sustainability;
  const blocks = blocksOf(read);
  // One investigation is written per close, so it sits under the first check that
  // asked for it rather than being repeated under every one.
  const firstProblem = report.checks.find((c) => c.result !== "pass")?.id ?? null;

  return (
    <article className="flex flex-col gap-8">
      <header className="border-b border-ink pb-3">
        <h2 className="font-condensed text-total">Period close</h2>
        <p className="text-caption text-ink-soft">
          {formatDate(report.period_start)} to {formatDate(report.period_end)}, prepared{" "}
          {formatDate(report.created_at)}
        </p>
      </header>

      {/* The memo sits under the title, where a reader meets the period in words
          before they meet it in columns. */}
      {blocks.memo ? <CloseMemo memo={blocks.memo} /> : null}

      <section>
        <SectionTitle right={<Total cents={report.write_off_total_cents} />}>
          Write-offs
        </SectionTitle>
        {report.write_offs.length === 0 ? (
          <p className="pt-2 text-body text-ink-soft">
            Nothing was written off in this period.
          </p>
        ) : (
          <table className="ledger w-full border-collapse text-body">
            <thead>
              <tr className="border-b border-rule text-caption text-ink-soft">
                <th className="py-1 font-normal">Item</th>
                <th className="py-1 text-right font-normal">Count</th>
                <th className="py-1 text-right font-normal">Mass</th>
                <th className="py-1 text-right font-normal">Amount ($)</th>
              </tr>
            </thead>
            <tbody>
              {report.write_offs.map((row) => (
                <tr key={row.label} className="h-row border-b border-rule hover:bg-bar">
                  <td>{row.label}</td>
                  <td className="text-right text-ink-soft">{formatCount(row.count)}</td>
                  <td className="text-right text-ink-soft">{formatMass(row.mass_g)}</td>
                  <td className="w-28 text-right">{formatMoney(row.cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <SectionTitle>Asset disposals</SectionTitle>
        {report.disposals.length === 0 ? (
          <p className="pt-2 text-body text-ink-soft">
            No tagged asset left the register in this period.
          </p>
        ) : (
          <>
            <table className="ledger w-full border-collapse text-body">
              <thead>
                <tr className="border-b border-rule text-caption text-ink-soft">
                  <th className="py-1 font-normal">Tag</th>
                  <th className="py-1 font-normal">Asset</th>
                  <th className="py-1 text-right font-normal">Book loss ($)</th>
                  <th className="py-1 text-right font-normal">Tax loss ($)</th>
                </tr>
              </thead>
              <tbody>
                {report.disposals.map((row) => (
                  <tr
                    key={`${row.tag ?? row.description}-${row.event_id}`}
                    className="h-row border-b border-rule hover:bg-bar"
                  >
                    <td className="font-condensed">{row.tag ? formatTag(row.tag) : ""}</td>
                    <td>
                      {row.event_id ? (
                        <Link
                          className="underline underline-offset-2"
                          href={`/events/${row.event_id}`}
                        >
                          {row.description}
                        </Link>
                      ) : (
                        row.description
                      )}
                    </td>
                    <td className="text-right">
                      <Money
                        cents={row.book_loss_cents}
                        eventId={row.event_id}
                        focus="book loss"
                      />
                    </td>
                    <td className="text-right">
                      <Money cents={row.tax_loss_cents} eventId={row.event_id} focus="tax loss" />
                    </td>
                  </tr>
                ))}
                <tr className="h-row border-t border-ink">
                  <td colSpan={2}>Totals</td>
                  <td className="text-right">
                    {formatMoney(report.disposal_book_loss_cents, { symbol: true })}
                  </td>
                  <td className="text-right">
                    {formatMoney(report.disposal_tax_loss_cents, { symbol: true })}
                  </td>
                </tr>
              </tbody>
            </table>
            {report.disposal_book_loss_cents !== report.disposal_tax_loss_cents ? (
              <p className="pt-2 text-caption text-ink-soft">
                The books lose more than the tax return does, because the bonus items were already
                fully expensed when they were bought.
              </p>
            ) : null}
          </>
        )}
      </section>

      {blocks.rollforward ? <Rollforward block={blocks.rollforward} /> : null}

      {blocks.reconciliation ? <Reconciliation block={blocks.reconciliation} /> : null}

      {blocks.form4797 ? <Form4797 block={blocks.form4797} /> : null}

      <section>
        <SectionTitle>Waste and emissions</SectionTitle>
        <p className="pb-2 text-caption text-ink-soft">
          Scope 3, Category 5 (waste generated in operations) inputs.
        </p>
        {green === null ? (
          <p className="text-body text-ink-soft">
            Nothing was scored for carbon in this period, so there is nothing to report.
          </p>
        ) : (
          <>
            <dl className="m-0 grid grid-cols-[minmax(0,1fr)_120px] gap-y-1">
              <Row label="To landfill">
                <Mass grams={green.kg_to_landfill * 1000} />
              </Row>
              <Row label="Kept from landfill if the best option had been followed">
                <Mass grams={green.kg_diverted_if_followed * 1000} />
              </Row>
              <Row label="Emissions as thrown">
                <Co2 kg={green.kg_co2e_actual} />
              </Row>
              <Row label="Emissions if the best option had been followed">
                <Co2 kg={green.kg_co2e_best} />
              </Row>
              <Row label="Cheapest option was also the greenest">
                <span>{formatPercent(green.cheapest_equals_greenest_pct / 100)}</span>
              </Row>
              <Row label="Electronics by mass">
                <Mass grams={green.kg_ewaste * 1000} />
              </Row>
            </dl>
            <p className="pt-2 text-caption text-ink-soft">
              Factors come from the EPA Waste Reduction Model. Resale, donation and repair are
              counted as source reduction, because they displace a new item.
              {green.events_without_carbon > 0
                ? ` ${formatCount(green.events_without_carbon)} tickets had no carbon factor and are left out.`
                : ""}
            </p>
          </>
        )}
      </section>

      <section>
        <SectionTitle right={<Total cents={report.missed_total_cents} />}>
          Missed opportunity
        </SectionTitle>
        {report.missed.length === 0 ? (
          <p className="pt-2 text-body text-ink-soft">
            Every ticket was already handled the best way it could have been.
          </p>
        ) : (
          <table className="ledger w-full border-collapse text-body">
            <tbody>
              {report.missed.map((row) => (
                <tr key={row.option ?? "other"} className="h-row border-b border-rule">
                  <td>{row.option ? formatOption(row.option) : "Other"}</td>
                  <td className="w-28 text-right">
                    <Money cents={row.cents} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <SectionTitle>Assets to review</SectionTitle>
        {report.ghosts.length === 0 ? (
          <p className="pt-2 text-body text-ink-soft">
            The register agrees with the bin. Nothing needs a look.
          </p>
        ) : (
          <ul className="m-0 list-none p-0">
            {report.ghosts.map((row) => (
              <li key={`${row.tag}-${row.description}`} className="border-b border-rule py-2">
                <p className="text-body">
                  <span className="font-condensed pr-2">{row.tag ? formatTag(row.tag) : ""}</span>
                  {row.description}
                </p>
                <p className="text-caption text-ink-soft">
                  Still marked as in use{row.location ? `, kept at ${row.location}` : ""}, but the
                  bin has seen it go.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <SectionTitle>Checks</SectionTitle>
        <ul className="m-0 list-none p-0">
          {report.checks.map((check) => (
            <CheckRow
              key={check.id}
              check={check}
              investigation={check.id === firstProblem ? report.investigation : null}
            />
          ))}
        </ul>
      </section>
    </article>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="contents">
      <dt className="border-b border-rule py-2 text-body">{label}</dt>
      <dd className="m-0 border-b border-rule py-2 text-right text-body">{children}</dd>
    </div>
  );
}

function Total({ cents }: { cents: number }) {
  return <span className="text-body">{formatMoney(cents, { symbol: true })}</span>;
}

function checkValue(number: CheckNumber): string {
  if (number.kind === "grams") return formatGrams(number.value);
  if (number.kind === "cents") return formatMoney(number.value);
  return formatCount(number.value);
}

function CheckRow({
  check,
  investigation,
}: {
  check: CloseCheck;
  investigation: string | null;
}) {
  const tone = check.result === "pass" ? "kept" : check.result === "warn" ? "caution" : "red";
  const word = check.result === "pass" ? "Pass" : check.result === "warn" ? "Warn" : "Fail";
  const prose = checkProse(check);
  const numbers = checkNumbers(check);
  const note = noteBlocks(investigation);

  return (
    <li className="border-b border-rule py-3">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-section">{checkName(check)}</span>
        <span className="flex items-center gap-2 text-body">
          <StatusDot tone={tone} />
          {word}
        </span>
      </div>
      {prose ? <p className="whitespace-pre-line pt-1 text-body text-ink-soft">{prose}</p> : null}
      {numbers.length > 0 ? (
        <dl className="m-0 grid max-w-[420px] grid-cols-[minmax(0,1fr)_120px] gap-y-1 pt-2">
          {numbers.map((n) => (
            <div key={n.label} className="contents">
              <dt className="text-body">{n.label}</dt>
              <dd className="m-0 text-right text-body">{checkValue(n)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {note.length > 0 ? (
        <div className={cx("mt-3 flex flex-col gap-1 border-l-2 border-red-ink pl-3")}>
          {note.map((block, i) => (
            <p key={i} className={block.kind === "heading" ? "text-section" : "text-body"}>
              {block.text}
            </p>
          ))}
        </div>
      ) : null}
    </li>
  );
}
