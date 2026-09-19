"use client";

import Link from "next/link";
import { useClose, useRunClose } from "@/lib/api";
import { formatDate, formatMass, formatMoney, formatPercent } from "@/lib/format";
import type { CloseCheck, CloseReport } from "@/lib/types";
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

export default function ClosePage() {
  const close = useClose();
  const run = useRunClose();

  return (
    <div className="max-w-[860px]">
      <PageHeader
        title="Close"
        right={
          <Button tone="primary" loading={run.isPending} onClick={() => run.mutate()}>
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

      {close.data === null && !close.isPending ? (
        <EmptyState
          title="No close yet for this period. Run one when the round is over."
          action={
            <Button tone="primary" onClick={() => run.mutate()}>
              Run close
            </Button>
          }
        />
      ) : null}

      {close.data ? <Statement report={close.data} /> : null}

      <FinanceFooter />
    </div>
  );
}

function Statement({ report }: { report: CloseReport }) {
  const writeOffTotal = report.write_offs.reduce((s, r) => s + r.amount_cents, 0);
  const bookLoss = report.disposals.reduce((s, r) => s + r.book_loss_cents, 0);
  const taxLoss = report.disposals.reduce((s, r) => s + r.tax_loss_cents, 0);
  const missed = report.missed.reduce((s, r) => s + r.amount_cents, 0);

  return (
    <article className="flex flex-col gap-8">
      <header className="border-b border-ink pb-3">
        <h2 className="font-condensed text-total">Period close</h2>
        <p className="text-caption text-ink-soft">
          {formatDate(report.period_start)} to {formatDate(report.period_end)}, prepared{" "}
          {formatDate(report.created_at)}
        </p>
      </header>

      <section>
        <SectionTitle right={<Total cents={writeOffTotal} />}>Write-offs</SectionTitle>
        <table className="ledger w-full border-collapse text-body">
          <tbody>
            {report.write_offs.map((row) => (
              <tr key={row.event_id} className="h-row border-b border-rule hover:bg-bar">
                <td>
                  <Link className="underline underline-offset-2" href={`/events/${row.event_id}`}>
                    {row.label}
                  </Link>
                </td>
                <td className="text-right text-ink-soft">{formatMass(row.mass_g)}</td>
                <td className="w-28 text-right">
                  <Money cents={row.amount_cents} eventId={row.event_id} focus="write-off" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <SectionTitle>Asset disposals</SectionTitle>
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
              <tr key={row.tag} className="h-row border-b border-rule hover:bg-bar">
                <td className="font-condensed">{row.tag}</td>
                <td>
                  <Link className="underline underline-offset-2" href={`/events/${row.event_id}`}>
                    {row.description}
                  </Link>
                </td>
                <td className="text-right">
                  <Money cents={row.book_loss_cents} eventId={row.event_id} focus="book loss" />
                </td>
                <td className="text-right">
                  <Money cents={row.tax_loss_cents} eventId={row.event_id} focus="tax loss" />
                </td>
              </tr>
            ))}
            <tr className="h-row border-t border-ink">
              <td colSpan={2}>Totals</td>
              <td className="text-right">{formatMoney(bookLoss, { symbol: true })}</td>
              <td className="text-right">{formatMoney(taxLoss, { symbol: true })}</td>
            </tr>
          </tbody>
        </table>
        <p className="pt-2 text-caption text-ink-soft">
          The books lose more than the tax return does, because the bonus items were already fully
          expensed when they were bought.
        </p>
      </section>

      <section>
        <SectionTitle>Tax items</SectionTitle>
        <table className="ledger w-full border-collapse text-body">
          <tbody>
            {report.tax_items.map((row) => (
              <tr key={row.label} className="h-row border-b border-rule">
                <td>{row.label}</td>
                <td className="text-ink-soft">{row.rule_id}</td>
                <td className="w-28 text-right">{formatMoney(row.amount_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <SectionTitle>Waste and emissions</SectionTitle>
        <p className="pb-2 text-caption text-ink-soft">
          Scope 3, Category 5 (waste generated in operations) inputs.
        </p>
        <dl className="m-0 grid grid-cols-[minmax(0,1fr)_120px] gap-y-1">
          <Row label="To landfill">
            <Mass grams={report.sustainability.kg_landfill * 1000} />
          </Row>
          <Row label="Kept from landfill if the best option had been followed">
            <Mass grams={report.sustainability.kg_diverted_if_followed * 1000} />
          </Row>
          <Row label="Emissions as thrown">
            <Co2 kg={report.sustainability.kg_co2e_actual} />
          </Row>
          <Row label="Emissions if the best option had been followed">
            <Co2 kg={report.sustainability.kg_co2e_best} />
          </Row>
          <Row label="Cheapest option was also the greenest">
            <span>{formatPercent(report.sustainability.cheapest_equals_greenest)}</span>
          </Row>
          <Row label="Electronics by mass">
            <Mass grams={report.sustainability.kg_ewaste * 1000} />
          </Row>
        </dl>
        <p className="pt-2 text-caption text-ink-soft">
          Factors come from the EPA Waste Reduction Model, version 16. Resale, donation and repair
          are counted as source reduction, because they displace a new item.
        </p>
      </section>

      <section>
        <SectionTitle right={<Total cents={missed} />}>Missed opportunity</SectionTitle>
        <table className="ledger w-full border-collapse text-body">
          <tbody>
            {report.missed.map((row) => (
              <tr key={row.option} className="h-row border-b border-rule">
                <td className="capitalize">{row.option}</td>
                <td className="w-28 text-right">
                  <Money cents={row.amount_cents} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <SectionTitle>Assets to review</SectionTitle>
        <ul className="m-0 list-none p-0">
          {report.ghost_assets.map((row) => (
            <li key={row.tag} className="border-b border-rule py-2">
              <p className="text-body">
                <span className="font-condensed pr-2">{row.tag}</span>
                {row.description}
              </p>
              <p className="text-caption text-ink-soft">{row.reason}</p>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>Checks</SectionTitle>
        <ul className="m-0 list-none p-0">
          {report.checks.map((check) => (
            <CheckRow key={check.id} check={check} />
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

function CheckRow({ check }: { check: CloseCheck }) {
  const tone = check.status === "pass" ? "kept" : check.status === "warn" ? "caution" : "red";
  const word = check.status === "pass" ? "Pass" : check.status === "warn" ? "Warn" : "Fail";
  return (
    <li className="border-b border-rule py-3">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-section">{check.name}</span>
        <span className="flex items-center gap-2 text-body">
          <StatusDot tone={tone} />
          {word}
        </span>
      </div>
      <p className="pt-1 text-body text-ink-soft">{check.detail}</p>
      {check.numbers.length > 0 ? (
        <dl className="m-0 grid max-w-[420px] grid-cols-[minmax(0,1fr)_120px] gap-y-1 pt-2">
          {check.numbers.map((n) => (
            <div key={n.label} className="contents">
              <dt className="text-body">{n.label}</dt>
              <dd className="m-0 text-right text-body">{n.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {check.investigation_md ? (
        <div className={cx("mt-3 border-l-2 border-red-ink pl-3")}>
          <p className="text-body">{check.investigation_md}</p>
          {check.suspect_event_ids.length > 0 ? (
            <p className="pt-1 text-caption text-ink-soft">
              Tickets to recount:{" "}
              {check.suspect_event_ids.map((id, i) => (
                <span key={id}>
                  {i > 0 ? ", " : ""}
                  <Link className="underline underline-offset-2" href={`/events/${id}`}>
                    {id}
                  </Link>
                </span>
              ))}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
