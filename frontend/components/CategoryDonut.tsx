"use client";

import type { CategoryBar } from "@/lib/derive";
import { formatMoney } from "@/lib/format";
import { cx } from "./ui";

/**
 * One colour per category, the same on the ring, the bars and the legend, so a
 * reader can carry a colour from one to the other. Green is not in the set: it
 * means money kept everywhere else in the product.
 */
export const CATEGORY_CLASS: Record<string, { fill: string; text: string; stroke: string }> = {
  food: { fill: "bg-cat-food", text: "text-cat-food", stroke: "stroke-cat-food" },
  packaging: { fill: "bg-cat-packaging", text: "text-cat-packaging", stroke: "stroke-cat-packaging" },
  equipment: { fill: "bg-cat-equipment", text: "text-cat-equipment", stroke: "stroke-cat-equipment" },
  "e-waste": { fill: "bg-cat-ewaste", text: "text-cat-ewaste", stroke: "stroke-cat-ewaste" },
  other: { fill: "bg-cat-other", text: "text-cat-other", stroke: "stroke-cat-other" },
};

const OTHER = { fill: "bg-cat-other", text: "text-cat-other", stroke: "stroke-cat-other" };

export function categoryClass(category: string): { fill: string; text: string; stroke: string } {
  return CATEGORY_CLASS[category] ?? OTHER;
}

/**
 * A ring of the period's money by category, drawn by hand as one stroked circle
 * per slice. The total sits in the middle, because that is the number a person
 * came for; the slices say where it went.
 *
 * A slice under 1.5 percent is still drawn, at a hair's width, so a category is
 * never silently missing from the ring while its row sits in the list beside it.
 */
export function CategoryDonut({ bars, className }: { bars: CategoryBar[]; className?: string }) {
  const total = bars.reduce((sum, bar) => sum + bar.cents, 0);
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const gap = bars.length > 1 ? 2.5 : 0;
  let offset = 0;
  const slices = bars.map((bar) => {
    const share = total > 0 ? bar.cents / total : 1 / bars.length;
    const length = Math.max(share * circumference - gap, 1.5);
    const slice = { bar, length, offset };
    offset += share * circumference;
    return slice;
  });

  return (
    <svg
      viewBox="0 0 160 160"
      className={cx("h-[180px] w-[180px] shrink-0", className)}
      role="img"
      aria-label={"Money by category, " + formatMoney(total, { symbol: true }) + " in all"}
    >
      <circle cx="80" cy="80" r={radius} fill="none" className="stroke-bar" strokeWidth="22" />
      {slices.map(({ bar, length, offset: at }) => (
        <circle
          key={bar.category}
          cx="80"
          cy="80"
          r={radius}
          fill="none"
          strokeWidth="22"
          className={categoryClass(bar.category).stroke}
          strokeDasharray={`${length} ${circumference - length}`}
          strokeDashoffset={-at}
          transform="rotate(-90 80 80)"
        />
      ))}
      <text
        x="80"
        y="76"
        textAnchor="middle"
        className="fill-ink font-condensed"
        style={{ fontSize: total >= 100000 ? 22 : 26, fontWeight: 600 }}
      >
        {formatMoney(total, { symbol: true })}
      </text>
      <text x="80" y="96" textAnchor="middle" className="fill-ink-soft" style={{ fontSize: 10.5 }}>
        in the bin
      </text>
    </svg>
  );
}
