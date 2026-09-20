"use client";

import { useState } from "react";
import { useRounds, useStats } from "@/lib/api";
import {
  categoryBars,
  statsEmpty,
  type CategoryBar,
  type StatsRange,
  type StatsResponse,
} from "@/lib/derive";
import { formatCount, formatMass, formatMoney, formatPercent } from "@/lib/format";
import { LearningChart } from "@/components/LearningChart";
import {
  EmptyState,
  ErrorState,
  FinanceFooter,
  PageHeader,
  SectionTitle,
  Skeleton,
  cx,
} from "@/components/ui";

const RANGES: { value: StatsRange; label: string }[] = [
  { value: "day", label: "By day" },
  { value: "week", label: "By week" },
];

export default function TrendsPage() {
  const [range, setRange] = useState<StatsRange>("day");
  const stats = useStats(range);
  const rounds = useRounds();
  const list = rounds.data?.rounds ?? [];
  const learned = rounds.data?.learned ?? [];
  const data = stats.data ?? null;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Trends"
        description="What has gone in the bin, what it cost, and where it came from."
        right={
          <div
            className="inline-flex rounded-control border border-control-border"
            role="group"
            aria-label="How far back each figure looks"
          >
            {RANGES.map((option, i) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setRange(option.value)}
                aria-pressed={range === option.value}
                className={cx(
                  "h-9 px-3 text-body transition-colors duration-fast ease-standard",
                  i === 0
                    ? "rounded-l-control"
                    : "rounded-r-control border-l border-control-border",
                  range === option.value ? "bg-ink text-paper" : "bg-surface text-ink hover:bg-bar",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />

      {stats.isPending ? <TrendsSkeleton /> : null}

      {stats.isError ? (
        <ErrorState
          title="The trends did not load. The backend is not answering."
          onRetry={() => stats.refetch()}
        />
      ) : null}

      {/* A backend older than the trends route answers 404, which arrives here as
          null. Nobody is told there was no waste when nobody was asked. */}
      {!stats.isPending && !stats.isError && data === null ? (
        <ErrorState
          title="Nothing is answering for the trends. The figures come from the bin's service, and it is not reporting them yet."
          onRetry={() => stats.refetch()}
        />
      ) : null}

      {data && statsEmpty(data) ? (
        <EmptyState title="No tosses in this range yet. Toss something in the bin and the totals, the averages and the categories fill in from the tickets." />
      ) : null}

      {data && !statsEmpty(data) ? <Figures stats={data} range={range} /> : null}

      <section>
        <SectionTitle>Right first try, and what it costs</SectionTitle>
        {rounds.isPending ? <Skeleton className="mt-3 h-[240px] w-full" /> : null}
        {rounds.isError ? (
          <div className="pt-3">
            <ErrorState
              title="The rounds did not load. The backend is not answering."
              onRetry={() => rounds.refetch()}
            />
          </div>
        ) : null}
        {rounds.data && list.length === 0 ? (
          <div className="pt-3">
            <EmptyState title="No rounds yet. The first round opens with the first toss, and the accuracy line starts there." />
          </div>
        ) : null}
        {list.length > 0 ? (
          <div className="pt-3">
            <LearningChart rounds={list} />
            <p className="pt-2 text-caption text-ink-soft">
              Cost per toss is on its own scale, which is why it is dashed.
            </p>
          </div>
        ) : null}
      </section>

      {learned.length > 0 ? (
        <section>
          <SectionTitle>What it learned</SectionTitle>
          <ul className="m-0 list-none p-0 pt-3">
            {learned.map((note) => (
              <li key={note} className="border-b border-rule py-2">
                <p className="text-body">{note}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <FinanceFooter />
    </div>
  );
}

function Figures({ stats, range }: { stats: StatsResponse; range: StatsRange }) {
  const bars = categoryBars(stats);
  const totals = stats.totals ?? {};
  const averages = stats.averages ?? {};
  const unit = range === "day" ? "day" : "week";
  const suggestions = stats.suggestions ?? [];

  return (
    <>
      <section aria-label="Totals">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 border-b border-rule pb-4 sm:grid-cols-4">
          <Figure
            label="Off the books"
            value={formatMoney(totals.wasted_cents ?? 0, { symbol: true })}
            under={formatMoney(averages.wasted_cents ?? 0, { symbol: true }) + " a " + unit}
          />
          <Figure
            label="Tosses"
            value={formatCount(totals.events ?? 0)}
            under={formatCount(Math.round(averages.events ?? 0)) + " a " + unit}
          />
          <Figure
            label="Kept from landfill"
            value={formatMass((totals.kg_diverted ?? 0) * 1000)}
            under={formatMass((averages.kg_diverted ?? 0) * 1000) + " a " + unit}
          />
          <Figure
            label="Saved if followed"
            value={formatMoney(totals.saved_if_followed_cents ?? 0, { symbol: true })}
            under={
              (totals.open_asks ?? 0) > 0
                ? formatCount(totals.open_asks ?? 0) + " still waiting on a person"
                : "Nothing waiting on a person"
            }
          />
        </div>
      </section>

      <section>
        <SectionTitle>Where it went</SectionTitle>
        <ul className="m-0 list-none p-0 pt-3">
          {bars.map((bar) => (
            <CategoryRow key={bar.category} bar={bar} total={totals.wasted_cents ?? 0} />
          ))}
        </ul>
      </section>

      {suggestions.length > 0 ? (
        <section>
          <SectionTitle>What the numbers say</SectionTitle>
          <ul className="m-0 list-none p-0 pt-3">
            {suggestions.map((line) => (
              <li key={line} className="border-b border-rule py-2">
                <p className="text-body">{line}</p>
              </li>
            ))}
          </ul>
          {stats.summary_md ? (
            <p className="max-w-[68ch] pt-4 text-body text-ink-soft">{stats.summary_md}</p>
          ) : null}
        </section>
      ) : null}
    </>
  );
}

function Figure({ label, value, under }: { label: string; value: string; under: string }) {
  return (
    <div>
      <p className="text-caption text-ink-soft">{label}</p>
      <p className="font-condensed text-total">{value}</p>
      <p className="text-caption text-ink-soft">{under}</p>
    </div>
  );
}

/**
 * A bar drawn by hand out of two blocks, because that is all a bar is and a chart
 * library would put its own look on it. The figure sits beside the label rather
 * than at the end of the bar, so a phone reads the numbers in one column.
 */
function CategoryRow({ bar, total }: { bar: CategoryBar; total: number }) {
  const share = total > 0 ? bar.cents / total : 0;
  return (
    <li className="border-b border-rule py-2">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-body">{bar.label}</span>
        <span className="text-body">
          {formatMoney(bar.cents, { symbol: true })}
          <span className="pl-2 text-caption text-ink-soft">{formatPercent(share)}</span>
        </span>
      </div>
      <div className="mt-1 h-2 w-full bg-bar" aria-hidden="true">
        <div className="h-2 bg-ink" style={{ width: Math.round(bar.share * 100) + "%" }} />
      </div>
      <p className="pt-1 text-caption text-ink-soft">
        {formatCount(bar.events)} {bar.events === 1 ? "toss" : "tosses"}, {formatMass(bar.massG)}
      </p>
    </li>
  );
}

function TrendsSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-4">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-2 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
