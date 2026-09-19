"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { API_URL, MOCK, emptyLive, keys, mockLive, useEvents } from "./api";
import type {
  EventSummary,
  UiAskOpened,
  UiDeviceStatus,
  UiMessage,
  SummaryResponse,
} from "./types";

export type TicketPhase = "weighing" | "identified";

export type LiveTicket = {
  event: EventSummary;
  phase: TicketPhase;
  /** Rises by one on every arrival, so the ticket can replay its motion. */
  arrival: number;
};

/** connecting until the socket opens, live while it is open, offline after it drops. */
export type LiveStatus = "connecting" | "live" | "offline";

export type DeviceState = { connected: boolean; detail: string | null };

export type LiveState = {
  status: LiveStatus;
  weight_g: number;
  /** Newest last. About 12 s of samples at 10 Hz. */
  samples: number[];
  /** Indices into samples where a ticket was cut. */
  steps: number[];
  tape: EventSummary[];
  ticket: LiveTicket | null;
  ask: UiAskOpened | null;
  bin: DeviceState;
  phone: DeviceState;
};

const OFFLINE: DeviceState = { connected: false, detail: null };

/** A status the pipeline only reaches once it knows what the thing was. */
function isIdentified(status: EventSummary["status"]): boolean {
  return status === "identified" || status === "confirmed" || status === "posted";
}

/**
 * One socket for the whole dashboard. It carries the topics in `UiMessage` and
 * nothing else. The list read on load fills the tape; everything after that
 * arrives here, so there is no polling flicker.
 */
export function useLive(): LiveState {
  const [state, setState] = useState<LiveState>(emptyLive);
  const client = useQueryClient();
  const events = useEvents();

  useEffect(() => {
    if (MOCK && mockLive) return mockLive(setState);
    return startSocket(setState, client);
  }, [client]);

  const fetched = events.data;
  return useMemo(() => {
    if (!fetched || fetched.length === 0) return state;
    const seen = new Set(state.tape.map((e) => e.id));
    const tape = [...state.tape, ...fetched.filter((e) => !seen.has(e.id))];
    tape.sort((a, b) => b.id - a.id);
    const ticket = state.ticket ?? tapeTicket(tape);
    return { ...state, tape, ticket };
  }, [state, fetched]);
}

/** On a page opened between tosses, the newest finished ticket is what to show. */
function tapeTicket(tape: EventSummary[]): LiveTicket | null {
  const newest = tape.find((event) => event.kind === "toss" && event.status !== "void");
  if (!newest) return null;
  return {
    event: newest,
    phase: isIdentified(newest.status) ? "identified" : "weighing",
    arrival: 0,
  };
}

function startSocket(
  setState: (fn: (prev: LiveState) => LiveState) => void,
  client: QueryClient,
): () => void {
  const url = API_URL.replace(/^http/, "ws") + "/ws/ui";
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const open = () => {
    socket = new WebSocket(url);
    socket.onopen = () => setState((prev) => ({ ...prev, status: "live" }));
    socket.onclose = () => {
      setState((prev) => ({
        ...prev,
        status: "offline",
        bin: { ...OFFLINE },
        phone: { ...OFFLINE },
      }));
      if (!closed) retry = setTimeout(open, 1500);
    };
    socket.onmessage = (raw) => {
      let message: UiMessage;
      try {
        message = JSON.parse(String(raw.data)) as UiMessage;
      } catch {
        return;
      }
      refresh(message, client);
      setState((prev) => reduce(prev, message));
    };
  };

  open();

  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    socket?.close();
  };
}

/**
 * The socket says what changed. The reads that draw it are refreshed here, so a
 * screen that is not the Live page still keeps up without polling.
 */
function refresh(message: UiMessage, client: QueryClient): void {
  switch (message.type) {
    case "event.created":
    case "event.updated":
      void client.invalidateQueries({ queryKey: keys.event(message.event.id) });
      void client.invalidateQueries({ queryKey: keys.events });
      return;
    case "journal.posted":
      void client.invalidateQueries({ queryKey: keys.journal });
      return;
    case "ask.resolved":
      void client.invalidateQueries({ queryKey: keys.event(message.event_id) });
      void client.invalidateQueries({ queryKey: keys.rounds });
      return;
    case "metrics.updated":
      client.setQueryData<SummaryResponse>(keys.summary, message.summary);
      void client.invalidateQueries({ queryKey: keys.rounds });
      return;
    default:
      return;
  }
}

function device(status: UiDeviceStatus): DeviceState {
  return { connected: status.connected, detail: status.detail ?? null };
}

function reduce(prev: LiveState, message: UiMessage): LiveState {
  switch (message.type) {
    case "weight": {
      const samples = [...prev.samples.slice(1), message.g];
      return {
        ...prev,
        weight_g: message.g,
        samples,
        steps: prev.steps.map((i) => i - 1).filter((i) => i >= 0),
      };
    }
    case "event.created": {
      const event = message.event;
      if (event.kind !== "toss") return { ...prev, tape: [event, ...prev.tape] };
      return {
        ...prev,
        tape: [event, ...prev.tape.filter((e) => e.id !== event.id)],
        steps: [...prev.steps.slice(-4), prev.samples.length - 1],
        ticket: { event, phase: "weighing", arrival: (prev.ticket?.arrival ?? 0) + 1 },
      };
    }
    case "event.updated": {
      const event = message.event;
      const tape = prev.tape.some((e) => e.id === event.id)
        ? prev.tape.map((e) => (e.id === event.id ? event : e))
        : [event, ...prev.tape];
      const ticket =
        prev.ticket && prev.ticket.event.id === event.id
          ? {
              ...prev.ticket,
              event,
              phase: isIdentified(event.status) ? ("identified" as const) : prev.ticket.phase,
            }
          : prev.ticket;
      return { ...prev, tape, ticket };
    }
    case "ask.opened":
      return { ...prev, ask: message };
    case "ask.resolved":
      return prev.ask && prev.ask.event_id === message.event_id
        ? { ...prev, ask: null }
        : prev;
    case "device.status":
      return message.device === "bin"
        ? { ...prev, bin: device(message) }
        : { ...prev, phone: device(message) };
    default:
      return prev;
  }
}
