"use client";

import { useState } from "react";
import { useRounds, useStats, useWaiting } from "@/lib/api";
import {
  categoryBars,
  statsAverages,
  statsEmpty,
  statsTotals,
  type CategoryBar,
  type StatsRange,
} from "@/lib/derive";
import type { StatsResponse } from "@/lib/types";
import { formatCount, formatDate, formatMass, formatMoney, formatPercent } from "@/lib/format";
import { waitingSentence } from "@/lib/copy";
import { AskBooks } from "@/components/AskBooks";
import { CategoryDonut, categoryClass } from "@/components/CategoryDonut";
import { LearningChart } from "@/components/LearningChart";
import {
  Badge,
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

      {/* The span the figures cover, said in dates, because "by day" on its own
          does not tell anyone how far back the totals reach. */}
      {data?.period_start && data?.period_end ? (
        <p className="-mt-6 text-caption text-ink-soft">
          {formatDate(data.period_start)} to {formatDate(data.period_end)}
          {data.averages?.days ? ", " + formatCount(Math.round(data.averages.days)) + " days" : ""}
        </p>
      ) : null}

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

      {/* The learning chart and what it learned sit side by side on a laptop, so
          the chart is not a lone line with a blank half page beside it. */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
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

        <section>
          <SectionTitle>What it learned</SectionTitle>
          {learned.length > 0 ? (
            <ul className="m-0 list-none p-0 pt-3">
              {learned.map((note) => (
                <li key={note} className="border-b border-rule py-2">
                  <p className="text-body">{note}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="pt-3 text-body text-ink-soft">
              Nothing corrected yet. Every answer a person gives at the bin lands here as a
              sentence, and the next toss of the same thing is recognised from it.
            </p>
          )}
        </section>
      </div>

      <FinanceFooter />
    </div>
  );
}

function Figures({ stats, range }: { stats: StatsResponse; range: StatsRange }) {
  const waiting = useWaiting();
  const bars = categoryBars(stats);
  const totals = statsTotals(stats);
  const averages = statsAverages(stats);
  const unit = range === "day" ? "day" : "week";
  const per = range === "day" ? 1 : 7;
  const suggestions = stats.suggestions ?? [];
  // The bars add up all three kinds of money, so the share a bar is a share of
  // has to be the same sum. Reading one of the three here would print a row at
  // 140 percent of the total and be wrong on the page nobody checks.
  const barTotal = bars.reduce((sum, bar) => sum + bar.cents, 0);

  return (
    <>
      <section aria-label="Totals">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 border-b border-rule pb-4 sm:grid-cols-4">
          <Figure
            label="Off the books"
            value={formatMoney(totals.wasted_cents, { symbol: true })}
            under={
              formatMoney(Math.round((averages.wasted_cents_per_day ?? 0) * per), {
                symbol: true,
              }) +
              " a " +
              unit
            }
          />
          <Figure
            label="Written off"
            value={formatMoney(totals.book_loss_cents, { symbol: true })}
            under={
              totals.book_loss_cents === 0
                ? "Nothing left the register"
                : "Book value of equipment that left the register"
            }
          />
          <Figure
            label="Tosses"
            value={formatCount(totals.tosses)}
            under={formatCount(Math.round((averages.tosses_per_day ?? 0) * per)) + " a " + unit}
          />
          <Figure
            label="To landfill"
            value={formatMass(totals.kg_landfill * 1000)}
            under={formatMass((averages.kg_per_day ?? 0) * per * 1000) + " a " + unit}
          />
        </div>
        <p className="pt-2 text-caption text-ink-soft">
          {/* The same count the rail and the tape print, read from the queue. */}
          {waitingSentence(waiting) + " "}
          {totals.kg_co2e_avoided > 0
            ? formatMass(totals.kg_co2e_avoided * 1000) +
              " of carbon stayed out of the air where the advice was followed."
            : ""}
        </p>
      </section>

      {/* Two columns on a laptop: where the money went on the left, what the
          numbers say and the question box on the right. One column on a phone. */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <section>
          <SectionTitle>Where it went</SectionTitle>
          <div className="flex flex-col gap-4 pt-3 sm:flex-row sm:items-start sm:gap-6">
            <CategoryDonut bars={bars} className="self-center sm:self-start" />
            <ul className="m-0 min-w-0 flex-1 list-none p-0">
              {bars.map((bar) => (
                <CategoryRow key={bar.category} bar={bar} total={barTotal} />
              ))}
            </ul>
          </div>
        </section>

        <div className="flex flex-col gap-8">
          {suggestions.length > 0 || stats.summary_md ? (
            <section>
              <SectionTitle>What the numbers say</SectionTitle>
              <ul className="m-0 list-none p-0 pt-3 empty:hidden">
                {suggestions.map((line) => (
                  <li key={line} className="border-b border-rule py-2">
                    <p className="text-body">{line}</p>
                  </li>
                ))}
              </ul>
              {stats.summary_md ? (
                <p className="pt-4 text-body text-ink-soft">{stats.summary_md}</p>
              ) : null}
            </section>
          ) : null}
          <AskBooks where="trends" />
        </div>
      </div>
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
 * than at the end of the bar, so a phone reads the numbers in one column. The bar
 * wears its category's colour, the same one its slice of the ring wears.
 */
function CategoryRow({ bar, total }: { bar: CategoryBar; total: number }) {
  const share = total > 0 ? bar.cents / total : 0;
  const colour = categoryClass(bar.category);
  return (
    <li className="border-b border-rule py-2">
      <div className="flex items-baseline justify-between gap-4">
        <span className="flex items-center gap-2 text-body">
          <span className={cx("inline-block h-2.5 w-2.5 rounded-full", colour.fill)} aria-hidden="true" />
          {bar.label}
        </span>
        <span className="text-body">
          {formatMoney(bar.cents, { symbol: true })}
          <Badge>{formatPercent(share)}</Badge>
        </span>
      </div>
      <div className="mt-1 h-2 w-full bg-bar" aria-hidden="true">
        <div className={cx("h-2", colour.fill)} style={{ width: Math.round(bar.share * 100) + "%" }} />
      </div>
      <p className="pt-1 text-caption text-ink-soft">
        {formatCount(bar.tosses)} {bar.tosses === 1 ? "toss" : "tosses"}, {formatMass(bar.massG)}
      </p>
    </li>
  );
}

function TrendsSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-hidden="true">
      <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col gap-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-28" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    </div>
  );
}
