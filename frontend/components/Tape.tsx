"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { EventSummary } from "@/lib/types";
import { ESTIMATE_MARKER, formatMoney, formatTime } from "@/lib/format";
import { useEvidence } from "./Providers";
import { EmptyState, cx } from "./ui";

/** The printed tape. Newest on top, one line each, j and k move, Enter opens. */
export function Tape({ events }: { events: EventSummary[] }) {
  const [selected, setSelected] = useState(0);
  const router = useRouter();
  const evidence = useEvidence();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.key === "j") setSelected((s) => Math.min(s + 1, events.length - 1));
      if (e.key === "k") setSelected((s) => Math.max(s - 1, 0));
      if (e.key === "Enter" && events[selected]) router.push(`/events/${events[selected].id}`);
      if (e.key === "e" && events[selected]) evidence.open(events[selected].id, "ticket total");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [events, selected, router, evidence]);

  if (events.length === 0) {
    return <EmptyState title="No tickets yet. Toss something in the bin, or run the simulator." />;
  }

  return (
    <ul className="m-0 list-none p-0">
      {events.map((event, i) => (
        <li key={event.id}>
          <button
            type="button"
            onClick={() => {
              setSelected(i);
              router.push(`/events/${event.id}`);
            }}
            className={cx(
              "flex h-row w-full items-center justify-between gap-2 border-b border-rule border-l-2 px-2 text-body transition-colors duration-fast ease-standard hover:bg-bar",
              i === selected ? "border-l-ink bg-bar" : "border-l-transparent",
            )}
          >
            <span className="flex min-w-0 items-baseline gap-2">
              <span className="truncate">{event.label ?? "Identifying"}</span>
              {event.is_estimate ? (
                <span className="text-caption text-ink-soft">{ESTIMATE_MARKER}</span>
              ) : null}
              {event.status === "asking" ? (
                <span className="text-caption text-caution">asking</span>
              ) : null}
            </span>
            <span className="flex shrink-0 items-baseline gap-3">
              <span className="text-caption text-ink-soft">{formatTime(event.created_at)}</span>
              {event.blocked ? (
                <span className="text-caption text-red-ink">blocked</span>
              ) : null}
              <span
                className={cx(
                  "w-20 text-right",
                  (event.book_amount_cents ?? 0) < 0 && "text-red-ink",
                )}
              >
                {event.book_amount_cents === null ? "" : formatMoney(event.book_amount_cents)}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
