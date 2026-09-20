"use client";

import type { TraceView } from "@/lib/derive";
import { formatMass } from "@/lib/format";

/**
 * The weight trace for one toss, with the step shaded.
 * Drawn by hand so it matches the live scale strip rather than a chart default.
 */
export function TraceChart({ trace, height = 72 }: { trace: TraceView; height?: number }) {
  const points = trace.points;
  if (points.length === 0) return null;
  const width = 360;
  const values = points.map((p) => p.g);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const first = points[0]?.t ?? 0;
  const last = points[points.length - 1]?.t ?? first + 1;
  const tSpan = Math.max(last - first, 0.001);
  const x = (t: number) => ((t - first) / tSpan) * width;
  const y = (g: number) => height - 6 - ((g - min) / span) * (height - 12);
  const path = points.map((p) => `${x(p.t).toFixed(1)},${y(p.g).toFixed(1)}`).join(" ");
  const openX = x(trace.open_t);
  const settleX = x(trace.settle_t);

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        preserveAspectRatio="none"
        role="img"
        aria-label={`Weight trace, settling at ${formatMass(trace.settled_g)}`}
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
        <line
          x1={settleX}
          y1={0}
          x2={settleX}
          y2={height}
          stroke="var(--control-border)"
          strokeWidth={1}
        />
      </svg>
      <figcaption className="pt-1 text-caption text-ink-soft">
        Shaded from the step opening to the settle. Step size is the difference of the two stable
        medians.
      </figcaption>
    </figure>
  );
}
