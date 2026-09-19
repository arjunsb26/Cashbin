"use client";

import { useEffect, useRef } from "react";
import { formatCount } from "@/lib/format";

/**
 * The live trace, drawn on a canvas so it stays smooth. Colours are read from the
 * token variables at paint time, so this file holds no colour of its own.
 */
export function ScaleStrip({
  samples,
  steps,
  weight_g,
  connected,
}: {
  samples: number[];
  steps: number[];
  weight_g: number;
  connected: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const parent = element.parentElement;
    if (!parent) return;
    const style = getComputedStyle(element);
    const ink = style.getPropertyValue("--ink").trim();
    const rule = style.getPropertyValue("--rule").trim();
    const border = style.getPropertyValue("--control-border").trim();

    const ratio = window.devicePixelRatio || 1;
    const width = parent.clientWidth;
    const height = 56;
    element.width = width * ratio;
    element.height = height * ratio;
    element.style.width = `${width}px`;
    element.style.height = `${height}px`;

    const ctx = element.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    if (samples.length === 0) return;
    const min = Math.min(...samples);
    const max = Math.max(...samples);
    // A fixed floor on the span, so a gram of sensor noise reads as a flat
    // instrument line instead of filling the strip with a sawtooth.
    const span = Math.max(max - min, 40);
    const x = (i: number) => (i / (samples.length - 1)) * width;
    const y = (g: number) => height - 8 - ((g - min) / span) * (height - 16);

    ctx.strokeStyle = rule;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height - 0.5);
    ctx.lineTo(width, height - 0.5);
    ctx.stroke();

    ctx.strokeStyle = connected ? ink : border;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    samples.forEach((g, i) => {
      if (i === 0) ctx.moveTo(x(i), y(g));
      else ctx.lineTo(x(i), y(g));
    });
    ctx.stroke();

    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    steps.forEach((i) => {
      const px = x(i);
      ctx.beginPath();
      ctx.moveTo(px, height - 14);
      ctx.lineTo(px, height - 2);
      ctx.stroke();
    });
  }, [samples, steps, connected]);

  return (
    <div className="flex flex-col gap-1 border-b border-rule py-3 sm:flex-row sm:items-center sm:gap-4">
      <div className="order-2 min-w-0 flex-1 sm:order-1">
        <canvas ref={canvas} aria-hidden="true" />
      </div>
      <div className="order-1 shrink-0 text-right sm:order-2">
        <span className="font-condensed text-total">{formatCount(Math.round(weight_g))}</span>
        <span className="pl-1 text-body text-ink-soft">g</span>
        <p className="text-caption text-ink-soft">
          {connected ? "Bin connected" : "Bin offline. Reconnecting."}
        </p>
      </div>
    </div>
  );
}
