"use client";

import { useEffect, useRef } from "react";
import type { Reach } from "@/lib/live";
import { asSentence, formatCount } from "@/lib/format";
import { StatusDot } from "./ui";

/** Ten samples a second, so thirty seconds is three hundred of them. */
const HZ = 10;
const SECONDS = 30;
const HEIGHT = 120;
/** Room under the trace for the time axis, and over it for the step labels. */
const PAD_TOP = 18;
const PAD_BOTTOM = 18;

/**
 * The live trace, drawn on a canvas so it stays smooth. Colours and the type size
 * are read from the token variables at paint time, so this file holds no colour
 * and no size of its own.
 */
export function ScaleStrip({
  samples,
  steps,
  stepMasses = [],
  weight_g,
  connected,
  reach = "live",
  detail = null,
}: {
  samples: number[];
  steps: number[];
  /** The mass each marked step weighed, in the same order as `steps`. */
  stepMasses?: number[];
  weight_g: number;
  connected: boolean;
  reach?: Reach;
  /** What the backend last said about the bin, when it said anything. */
  detail?: string | null;
}) {
  const canvas = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const parent = element.parentElement;
    if (!parent) return;
    const draw = () => paint(element, parent);
    draw();
    // The column is a flex child, so its width is not settled on the first paint.
    // A canvas sized then keeps its pixel width and runs on under the reading and
    // its status line. Redrawing on every resize keeps the trace inside its column.
    const observer = new ResizeObserver(draw);
    observer.observe(parent);
    return () => observer.disconnect();
  });

  function paint(element: HTMLCanvasElement, parent: HTMLElement) {
    const style = getComputedStyle(element);
    const ink = style.getPropertyValue("--ink").trim();
    const soft = style.getPropertyValue("--ink-soft").trim();
    const rule = style.getPropertyValue("--rule").trim();
    const border = style.getPropertyValue("--control-border").trim();
    const caption = style.getPropertyValue("--size-caption").trim() || "12.5px";
    const family = style.fontFamily;

    const ratio = window.devicePixelRatio || 1;
    const width = parent.clientWidth;
    element.width = width * ratio;
    element.height = HEIGHT * ratio;
    element.style.width = `${width}px`;
    element.style.height = `${HEIGHT}px`;

    const ctx = element.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, HEIGHT);

    // The window is always thirty seconds wide, whatever has arrived so far, so
    // the trace scrolls in from the right rather than stretching to fit.
    const span = SECONDS * HZ;
    const shown = samples.slice(-span);
    const offset = span - shown.length;
    const x = (i: number) => ((offset + i) / (span - 1)) * width;

    const floor = HEIGHT - PAD_BOTTOM;
    ctx.font = `${caption} ${family}`;
    ctx.fillStyle = soft;

    // The axis: thirty seconds back on the left, now on the right.
    ctx.strokeStyle = rule;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, floor + 0.5);
    ctx.lineTo(width, floor + 0.5);
    ctx.stroke();

    for (let s = 0; s <= SECONDS; s += 10) {
      const px = ((SECONDS - s) / SECONDS) * width;
      ctx.beginPath();
      ctx.moveTo(px, floor);
      ctx.lineTo(px, floor + 4);
      ctx.stroke();
      const label = s === 0 ? "now" : `${s} s`;
      ctx.textAlign = s === SECONDS ? "left" : s === 0 ? "right" : "center";
      ctx.fillText(label, px, HEIGHT - 4);
    }

    if (shown.length < 2) return;

    const min = Math.min(...shown);
    const max = Math.max(...shown);
    // A fixed floor on the vertical span, so a gram of sensor noise reads as a
    // flat instrument line instead of filling the strip with a sawtooth.
    const range = Math.max(max - min, 40);
    const y = (g: number) => floor - 6 - ((g - min) / range) * (floor - PAD_TOP - 6);

    ctx.strokeStyle = connected ? ink : border;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    shown.forEach((g, i) => {
      if (i === 0) ctx.moveTo(x(i), y(g));
      else ctx.lineTo(x(i), y(g));
    });
    ctx.stroke();

    // Every detected step gets a tick and the mass it weighed, because the mass
    // is the whole reason the step matters.
    const dropped = samples.length - shown.length;
    steps.forEach((index, n) => {
      const i = index - dropped;
      if (i < 0 || i >= shown.length) return;
      const px = x(i);
      ctx.strokeStyle = border;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px, PAD_TOP);
      ctx.lineTo(px, floor);
      ctx.stroke();
      const mass = stepMasses[n];
      if (mass === undefined) return;
      ctx.fillStyle = soft;
      ctx.textAlign = px > width - 48 ? "right" : "left";
      ctx.fillText(`${Math.round(mass)} g`, px > width - 48 ? px - 4 : px + 4, PAD_TOP - 5);
    });
  }

  const line =
    reach === "connecting"
      ? "Connecting to the bin."
      : reach === "dead"
        ? "No reading. Nothing is answering."
        : connected
          ? "Bin connected"
          : detail
            ? asSentence(detail)
            : "Bin offline. Reconnecting.";
  const tone =
    reach === "dead" ? "red" : reach === "connecting" ? "soft" : connected ? "kept" : "caution";

  return (
    <div className="flex flex-col gap-1 border-b border-rule py-3 sm:flex-row sm:items-end sm:gap-4">
      <div className="order-2 min-w-0 flex-1 sm:order-1">
        <canvas ref={canvas} aria-hidden="true" />
      </div>
      <div className="order-1 shrink-0 text-right sm:order-2 sm:pb-5">
        <span className="font-condensed text-total">{formatCount(Math.round(weight_g))}</span>
        <span className="pl-1 text-body text-ink-soft">g</span>
        <p className="flex items-center justify-end gap-2 text-caption text-ink-soft">
          <StatusDot tone={tone} />
          {line}
        </p>
      </div>
    </div>
  );
}
