"use client";

import type { Round } from "@/lib/types";
import { formatMicroUsd, formatPercent } from "@/lib/format";

/**
 * Drawn by hand: faint horizontal rules, no legend box, each line labelled at its
 * right end in its own colour. Percentages share the left scale. Cost has its own
 * scale, so it is dashed and labelled with its value.
 */
export function LearningChart({ rounds }: { rounds: Round[] }) {
  const width = 900;
  const height = 280;
  const padLeft = 40;
  const padRight = 150;
  const padTop = 16;
  const padBottom = 32;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const maxCost = Math.max(...rounds.map((r) => r.cost_per_event_microusd), 1);
  const x = (i: number) =>
    padLeft + (rounds.length === 1 ? plotWidth / 2 : (i / (rounds.length - 1)) * plotWidth);
  const yPercent = (v: number) => padTop + (1 - v) * plotHeight;
  const yCost = (v: number) => padTop + (1 - v / maxCost) * plotHeight;

  const line = (points: string[]) => points.join(" ");
  const accuracy = line(rounds.map((r, i) => `${x(i)},${yPercent(r.first_try_accuracy)}`));
  const asked = line(rounds.map((r, i) => `${x(i)},${yPercent(r.ask_rate)}`));
  const cost = line(rounds.map((r, i) => `${x(i)},${yCost(r.cost_per_event_microusd)}`));
  const last = rounds[rounds.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-auto w-full"
      role="img"
      aria-label="Right first try, asked a person, and cost per toss, by round"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line
            x1={padLeft}
            y1={yPercent(v)}
            x2={padLeft + plotWidth}
            y2={yPercent(v)}
            stroke="var(--rule)"
            strokeWidth={1}
          />
          <text
            x={padLeft - 8}
            y={yPercent(v) + 4}
            textAnchor="end"
            fill="var(--ink-soft)"
            fontSize={12.5}
          >
            {formatPercent(v)}
          </text>
        </g>
      ))}

      {rounds.map((round, i) => (
        <text
          key={round.id}
          x={x(i)}
          y={height - 10}
          textAnchor="middle"
          fill="var(--ink-soft)"
          fontSize={12.5}
        >
          Round {round.id}
        </text>
      ))}

      <polyline points={accuracy} fill="none" stroke="var(--ink)" strokeWidth={2} />
      <polyline points={asked} fill="none" stroke="var(--ink-soft)" strokeWidth={1.5} />
      <polyline
        points={cost}
        fill="none"
        stroke="var(--ink-soft)"
        strokeWidth={1.5}
        strokeDasharray="4 3"
      />

      {rounds.map((round, i) => (
        <circle key={round.id} cx={x(i)} cy={yPercent(round.first_try_accuracy)} r={2.5} fill="var(--ink)" />
      ))}

      {last ? (
        <>
          <text
            x={padLeft + plotWidth + 10}
            y={yPercent(last.first_try_accuracy) + 4}
            fill="var(--ink)"
            fontSize={12.5}
          >
            Right first try {formatPercent(last.first_try_accuracy)}
          </text>
          <text
            x={padLeft + plotWidth + 10}
            y={yPercent(last.ask_rate) + 4}
            fill="var(--ink-soft)"
            fontSize={12.5}
          >
            Asked a person {formatPercent(last.ask_rate)}
          </text>
          <text
            x={padLeft + plotWidth + 10}
            y={yCost(last.cost_per_event_microusd) + 4}
            fill="var(--ink-soft)"
            fontSize={12.5}
          >
            Cost per toss ${formatMicroUsd(last.cost_per_event_microusd)}
          </text>
        </>
      ) : null}
    </svg>
  );
}
