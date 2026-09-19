// The scripted live sequence. It replays the demo tosses on a timer so the ticket
// arrival can be watched and screenshotted. Reached only through lib/api.ts.
import * as fx from "./fixtures";
import { askOpen, mockState, replayOn } from "./state";
import type { EventDetail } from "../types";
import type { LiveState, TicketPhase } from "../live";

const WINDOW = 120;
const BASELINE = 2412;
const OFFLINE = { bin: "offline", phone: "offline", last_weight_g: 0 } as const;

export function flatSamples(base: number): number[] {
  return Array.from({ length: WINDOW }, (_, i) => base + Math.sin(i * 1.7) * 0.8);
}

export function emptyLiveState(): LiveState {
  return {
    connected: false,
    weight_g: 0,
    samples: flatSamples(0),
    steps: [],
    tape: [],
    ticket: null,
    ask: null,
    device: { ...OFFLINE },
  };
}

/** Drives the live state from fixtures. Returns the teardown. */
export function startMockLive(
  setState: (fn: (prev: LiveState) => LiveState) => void,
): () => void {
  const timers: ReturnType<typeof setInterval>[] = [];
  const view = mockState();

  if (view === "loading" || view === "error" || view === "empty") {
    setState(() => ({
      ...emptyLiveState(),
      connected: view !== "error",
      device:
        view === "error"
          ? { ...OFFLINE }
          : { bin: "connected", phone: "connected", last_weight_g: 0 },
    }));
    return () => {};
  }

  const order = [102, 101, 103, 104];
  const seeded = fx.EVENT_DETAILS[102] as EventDetail;
  const asking = fx.EVENT_DETAILS[105] as EventDetail;
  const showAsk = askOpen();

  setState(() => ({
    connected: true,
    weight_g: BASELINE,
    samples: flatSamples(BASELINE),
    steps: [42, 78],
    tape: fx.EVENTS,
    ticket: showAsk
      ? { detail: asking, phase: "weighing" as TicketPhase, arrival: 0 }
      : { detail: seeded, phase: "identified" as TicketPhase, arrival: 0 },
    ask: showAsk ? asking.ask : null,
    device: { bin: "connected", phone: "connected", last_weight_g: BASELINE },
  }));

  // The scale never stops reading.
  timers.push(
    setInterval(() => {
      setState((prev) => {
        const last = prev.samples[prev.samples.length - 1] ?? BASELINE;
        const next = [...prev.samples.slice(1), last + (Math.random() - 0.5) * 1.2];
        return { ...prev, samples: next, weight_g: next[next.length - 1] ?? BASELINE };
      });
    }, 100),
  );

  if (replayOn()) {
    let index = 0;
    timers.push(
      setInterval(() => {
        const id = order[index % order.length] as number;
        const detail = fx.EVENT_DETAILS[id] as EventDetail;
        index += 1;
        setState((prev) => {
          const last = prev.samples[prev.samples.length - 1] ?? BASELINE;
          const next = [...prev.samples.slice(1), last + detail.event.mass_g];
          return {
            ...prev,
            samples: next,
            weight_g: next[next.length - 1] ?? BASELINE,
            steps: [...prev.steps.slice(-4), next.length - 1],
            ticket: {
              detail,
              phase: "weighing" as TicketPhase,
              arrival: (prev.ticket?.arrival ?? 0) + 1,
            },
            tape: [detail.event, ...prev.tape.filter((e) => e.id !== detail.event.id)],
          };
        });
        setTimeout(() => {
          setState((prev) =>
            prev.ticket && prev.ticket.detail.event.id === id
              ? { ...prev, ticket: { ...prev.ticket, phase: "identified" as TicketPhase } }
              : prev,
          );
        }, 700);
      }, 9000),
    );
  }

  return () => timers.forEach(clearInterval);
}
