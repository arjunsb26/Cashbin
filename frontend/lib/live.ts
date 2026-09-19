"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL, MOCK } from "./api";
import { fixtures, mockState, replayOn, askOpen } from "./mock";
import type { AskState, DeviceStatus, EventDetail, EventSummary, UiMessage } from "./types";

export type TicketPhase = "weighing" | "identified";

export type LiveTicket = {
  detail: EventDetail;
  phase: TicketPhase;
  /** Rises by one on every arrival, so the ticket can replay its motion. */
  arrival: number;
};

export type LiveState = {
  connected: boolean;
  weight_g: number;
  /** Newest last. About 12 s of samples at 10 Hz. */
  samples: number[];
  /** Indices into samples where a step was detected. */
  steps: number[];
  tape: EventSummary[];
  ticket: LiveTicket | null;
  ask: AskState | null;
  device: DeviceStatus;
};

const WINDOW = 120;
const BASELINE = 2412;

function flatSamples(base: number): number[] {
  return Array.from({ length: WINDOW }, (_, i) => base + Math.sin(i * 1.7) * 0.8);
}

const OFFLINE: DeviceStatus = { bin: "offline", phone: "offline", last_weight_g: 0 };

function emptyState(): LiveState {
  return {
    connected: false,
    weight_g: 0,
    samples: flatSamples(0),
    steps: [],
    tape: [],
    ticket: null,
    ask: null,
    device: OFFLINE,
  };
}

/**
 * One socket for the whole dashboard, PLAN.md section 6 topics.
 * In mock mode the same state is produced from fixtures, and with ?replay=1 the
 * demo tosses arrive on a timer so the ticket motion can be watched.
 */
export function useLive(): LiveState {
  const [state, setState] = useState<LiveState>(emptyState);
  const timers = useRef<ReturnType<typeof setInterval>[]>([]);

  useEffect(() => {
    if (MOCK) return startMock(setState, timers);
    return startSocket(setState);
  }, []);

  return state;
}

function startMock(
  setState: (fn: (prev: LiveState) => LiveState) => void,
  timers: { current: ReturnType<typeof setInterval>[] },
): () => void {
  const view = mockState();
  if (view === "loading" || view === "error" || view === "empty") {
    setState(() => ({
      ...emptyState(),
      connected: view !== "error",
      device: view === "error" ? OFFLINE : { bin: "connected", phone: "connected", last_weight_g: 0 },
      samples: flatSamples(view === "empty" ? 0 : 0),
    }));
    return () => {};
  }

  const order = [102, 101, 103, 104];
  const seeded = fixtures.EVENT_DETAILS[102] as EventDetail;
  const asking = fixtures.EVENT_DETAILS[105] as EventDetail;
  const showAsk = askOpen();

  setState(() => ({
    connected: true,
    weight_g: BASELINE,
    samples: flatSamples(BASELINE),
    steps: [42, 78],
    tape: fixtures.EVENTS,
    ticket: showAsk
      ? { detail: asking, phase: "weighing", arrival: 0 }
      : { detail: seeded, phase: "identified", arrival: 0 },
    ask: showAsk ? asking.ask : null,
    device: { bin: "connected", phone: "connected", last_weight_g: BASELINE },
  }));

  // The scale never stops reading.
  const tick = setInterval(() => {
    setState((prev) => {
      const last = prev.samples[prev.samples.length - 1] ?? BASELINE;
      const next = [...prev.samples.slice(1), last + (Math.random() - 0.5) * 1.2];
      return { ...prev, samples: next, weight_g: next[next.length - 1] ?? BASELINE };
    });
  }, 100);
  timers.current.push(tick);

  if (replayOn()) {
    let index = 0;
    const replay = setInterval(() => {
      const id = order[index % order.length] as number;
      const detail = fixtures.EVENT_DETAILS[id] as EventDetail;
      index += 1;
      setState((prev) => {
        const last = prev.samples[prev.samples.length - 1] ?? BASELINE;
        const next = [...prev.samples.slice(1), last + detail.event.mass_g];
        return {
          ...prev,
          samples: next,
          weight_g: next[next.length - 1] ?? BASELINE,
          steps: [...prev.steps.slice(-4), next.length - 1],
          ticket: { detail, phase: "weighing", arrival: (prev.ticket?.arrival ?? 0) + 1 },
          tape: [detail.event, ...prev.tape.filter((e) => e.id !== detail.event.id)],
        };
      });
      setTimeout(() => {
        setState((prev) =>
          prev.ticket && prev.ticket.detail.event.id === id
            ? { ...prev, ticket: { ...prev.ticket, phase: "identified" } }
            : prev,
        );
      }, 700);
    }, 9000);
    timers.current.push(replay);
  }

  return () => {
    timers.current.forEach(clearInterval);
    timers.current = [];
  };
}

function startSocket(setState: (fn: (prev: LiveState) => LiveState) => void): () => void {
  const url = API_URL.replace(/^http/, "ws") + "/ws/ui";
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const open = () => {
    socket = new WebSocket(url);
    socket.onopen = () => setState((prev) => ({ ...prev, connected: true }));
    socket.onclose = () => {
      setState((prev) => ({ ...prev, connected: false, device: OFFLINE }));
      if (!closed) retry = setTimeout(open, 1500);
    };
    socket.onmessage = (raw) => {
      let message: UiMessage;
      try {
        message = JSON.parse(String(raw.data)) as UiMessage;
      } catch {
        return;
      }
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

function reduce(prev: LiveState, message: UiMessage): LiveState {
  switch (message.type) {
    case "weight": {
      const samples = [...prev.samples.slice(1), message.g];
      return {
        ...prev,
        weight_g: message.g,
        samples,
        steps: message.step ? [...prev.steps.slice(-4), samples.length - 1] : prev.steps,
      };
    }
    case "event.created":
      return { ...prev, tape: [message.event, ...prev.tape] };
    case "event.updated": {
      const tape = prev.tape.map((e) => (e.id === message.event.id ? message.event : e));
      const ticket = message.detail
        ? {
            detail: message.detail,
            phase: "identified" as TicketPhase,
            arrival: (prev.ticket?.arrival ?? 0) + 1,
          }
        : prev.ticket;
      return { ...prev, tape, ticket };
    }
    case "ask.opened":
      return { ...prev, ask: message.ask };
    case "ask.resolved":
      return { ...prev, ask: null };
    case "device.status":
      return { ...prev, device: message.status };
    default:
      return prev;
  }
}
