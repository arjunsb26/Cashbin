"use client";

import { useEffect, useState } from "react";
import { API_URL, MOCK, emptyLive, mockLive } from "./api";
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

const OFFLINE: DeviceStatus = { bin: "offline", phone: "offline", last_weight_g: 0 };

/**
 * One socket for the whole dashboard, PLAN.md section 6 topics.
 * In mock mode the same state is produced from fixtures, and with ?replay=1 the
 * demo tosses arrive on a timer so the ticket motion can be watched.
 */
export function useLive(): LiveState {
  const [state, setState] = useState<LiveState>(emptyLive);

  useEffect(() => {
    if (MOCK && mockLive) return mockLive(setState);
    return startSocket(setState);
  }, []);

  return state;
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
