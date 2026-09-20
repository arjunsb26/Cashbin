"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { EventDetail, EventSummary } from "@/lib/types";
import { tapeAmount, trashBlocked } from "@/lib/derive";
import { ESTIMATE_MARKER, formatMoney, formatTime } from "@/lib/format";
import { fromEditable } from "@/lib/keys";
import { useEvidence } from "./Providers";
import { EmptyState, cx } from "./ui";

/** The printed tape. Newest on top, one line each, j and k move, Enter opens. */
export function Tape({
  events,
  details,
}: {
  events: EventSummary[];
  details: Map<number, EventDetail>;
}) {
  const [selected, setSelected] = useState(0);
  const router = useRouter();
  const evidence = useEvidence();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (fromEditable(e.target)) return;
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
          <TapeRow
            event={event}
            detail={details.get(event.id) ?? null}
            selected={i === selected}
            onOpen={() => {
              setSelected(i);
              router.push(`/events/${event.id}`);
            }}
          />
        </li>
      ))}
    </ul>
  );
}

function TapeRow({
  event,
  detail,
  selected,
  onOpen,
}: {
  event: EventSummary;
  detail: EventDetail | null;
  selected: boolean;
  onOpen: () => void;
}) {
  const figure = tapeAmount(event, detail?.item_record);
  const blocked = trashBlocked(detail?.options);
  const pending = event.status === "asking" || event.status === "detected";

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cx(
        "flex h-row w-full items-center justify-between gap-2 border-b border-rule border-l-2 px-2 text-body transition-colors duration-fast ease-standard hover:bg-bar",
        selected ? "border-l-ink bg-bar" : "border-l-transparent",
      )}
    >
      <span className="flex min-w-0 items-baseline gap-2">
        <span className="truncate">{event.label ?? labelFor(event)}</span>
        {figure.estimate ? (
          <span className="text-caption text-ink-soft">{ESTIMATE_MARKER}</span>
        ) : null}
        {event.status === "asking" ? (
          <span className="text-caption text-caution">asking</span>
        ) : null}
        {event.status === "void" ? (
          <span className="text-caption text-ink-soft">void</span>
        ) : null}
      </span>
      <span className="flex shrink-0 items-baseline gap-3">
        <span className="text-caption text-ink-soft">{formatTime(event.created_at)}</span>
        {blocked ? <span className="text-caption text-red-ink">blocked</span> : null}
        <span className={cx("w-20 text-right", figure.cents < 0 && "text-red-ink")}>
          {event.kind !== "toss" ? (
            <span className="text-caption text-ink-soft">no entry</span>
          ) : pending || !figure.known ? (
            <span className="text-caption text-ink-soft">{pending ? "pending" : "no entry"}</span>
          ) : (
            formatMoney(figure.cents)
          )}
        </span>
      </span>
    </button>
  );
}

/** A row with no label yet still says what it is, because the kind is known first. */
function labelFor(event: EventSummary): string {
  if (event.kind === "bag_change") return "Bag change";
  if (event.kind === "removal") return "Taken back out";
  return "Identifying";
}
