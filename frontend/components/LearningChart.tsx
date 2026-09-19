"use client";

import { useEffect, useRef, useState } from "react";
import type { RoundRead } from "@/lib/types";
import { formatMicroUsd, formatPercent } from "@/lib/format";

/**
 * Drawn by hand: faint horizontal rules, no legend box, each line labelled at its
 * right end in its own colour. Percentages share the left scale. Cost has its own
 * scale, so it is dashed and labelled with its value.
 *
 * A round that has not scored yet leaves a gap rather than a line to zero, which
 * would read as a collapse in accuracy that never happened.
 */
export function LearningChart({ rounds }: { rounds: RoundRead[] }) {
  const host = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(900);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(element.clientWidth, 480));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const height = 280;
  const padLeft = 40;
  const padRight = 150;
  const padTop = 16;
  const padBottom = 32;
  const plotWidth = width - padLeft - padRight;
  const plotHeight = height - padTop - padBottom;

  const costs = rounds.map((r) => r.cost_per_event_microusd ?? 0);
  const maxCost = Math.max(...costs, 1);
  const x = (i: number) =>
    padLeft + (rounds.length === 1 ? plotWidth / 2 : (i / (rounds.length - 1)) * plotWidth);
  const yPercent = (v: number) => padTop + (1 - v) * plotHeight;
  const yCost = (v: number) => padTop + (1 - v / maxCost) * plotHeight;

  const line = (pick: (r: RoundRead) => number | null | undefined, scale: (v: number) => number) =>
    rounds
      .map((round, i) => ({ value: pick(round), i }))
      .filter((p) => p.value !== null && p.value !== undefined)
      .map((p) => `${x(p.i)},${scale(p.value as number)}`)
      .join(" ");

  const accuracy = line((r) => r.first_try_accuracy, yPercent);
  const asked = line((r) => r.ask_rate, yPercent);
  const cost = line((r) => r.cost_per_event_microusd, yCost);
  const last = rounds[rounds.length - 1];

  return (
    <div ref={host}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
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

        {rounds.map((round, i) =>
          round.first_try_accuracy === null || round.first_try_accuracy === undefined ? null : (
            <circle
              key={round.id}
              cx={x(i)}
              cy={yPercent(round.first_try_accuracy)}
              r={2.5}
              fill="var(--ink)"
            />
          ),
        )}

        {last ? (
          <>
            {last.first_try_accuracy !== null && last.first_try_accuracy !== undefined ? (
              <text
                x={padLeft + plotWidth + 10}
                y={yPercent(last.first_try_accuracy) + 4}
                fill="var(--ink)"
                fontSize={12.5}
              >
                Right first try {formatPercent(last.first_try_accuracy)}
              </text>
            ) : null}
            {last.ask_rate !== null && last.ask_rate !== undefined ? (
              <text
                x={padLeft + plotWidth + 10}
                y={yPercent(last.ask_rate) + 4}
                fill="var(--ink-soft)"
                fontSize={12.5}
              >
                Asked a person {formatPercent(last.ask_rate)}
              </text>
            ) : null}
            {last.cost_per_event_microusd !== null &&
            last.cost_per_event_microusd !== undefined ? (
              <text
                x={padLeft + plotWidth + 10}
                y={yCost(last.cost_per_event_microusd) + 4}
                fill="var(--ink-soft)"
                fontSize={12.5}
              >
                Cost per toss ${formatMicroUsd(last.cost_per_event_microusd)}
              </text>
            ) : null}
          </>
        ) : null}
      </svg>
    </div>
  );
}
