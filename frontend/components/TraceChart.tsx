"use client";

import type { WeightTrace } from "@/lib/types";
import { formatMass } from "@/lib/format";

/**
 * The weight trace for one toss, with the settle window shaded.
 * Drawn by hand so it matches the live scale strip rather than a chart default.
 */
export function TraceChart({ trace, height = 72 }: { trace: WeightTrace; height?: number }) {
  const points = trace.points;
  if (points.length === 0) return null;
  const width = 360;
  const values = points.map((p) => p.g);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const tMax = points[points.length - 1]?.t_ms ?? 1;
  const x = (t: number) => (t / tMax) * width;
  const y = (g: number) => height - 6 - ((g - min) / span) * (height - 12);
  const path = points.map((p) => `${x(p.t_ms).toFixed(1)},${y(p.g).toFixed(1)}`).join(" ");
  const openX = x(trace.open_t_ms);
  const settleX = x(trace.settle_t_ms);

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`Weight trace, settling at ${formatMass(values[values.length - 1] ?? 0)}`}
      >
        <rect
          x={openX}
          y={0}
          width={Math.max(settleX - openX, 2)}
          height={height}
          fill="var(--bar)"
        />
        <line
          x1={0}
          y1={y(trace.baseline_g)}
          x2={width}
          y2={y(trace.baseline_g)}
          stroke="var(--rule)"
          strokeWidth={1}
        />
        <polyline points={path} fill="none" stroke="var(--ink)" strokeWidth={1.5} />
        <line x1={settleX} y1={0} x2={settleX} y2={height} stroke="var(--control-border)" strokeWidth={1} />
      </svg>
      <figcaption className="pt-1 text-caption text-ink-soft">
        Shaded from the step opening to the settle. Step size is the difference of the two stable
        medians.
      </figcaption>
    </figure>
  );
}
