// The scripted live sequence. It replays the demo tosses on a timer so the ticket
// arrival can be watched and screenshotted. Reached only through lib/api.ts.
import * as fx from "./fixtures";
import { askOpen, mockState, replayOn } from "./state";
import type { EventSummary } from "../types";
import type { DeviceState, LiveState, LiveStatus } from "../live";

const WINDOW = 120;
const BASELINE = 2412;
const OFF: DeviceState = { connected: false, detail: null };
const ON: DeviceState = { connected: true, detail: null };

export function flatSamples(base: number): number[] {
  return Array.from({ length: WINDOW }, (_, i) => base + Math.sin(i * 1.7) * 0.8);
}

export function emptyLiveState(): LiveState {
  return {
    status: "connecting",
    weight_g: 0,
    samples: Array.from({ length: WINDOW }, () => 0),
    steps: [],
    tape: [],
    ticket: null,
    ask: null,
    bin: { ...OFF },
    phone: { ...OFF },
  };
}

/** Drives the live state from fixtures. Returns the teardown. */
export function startMockLive(
  setState: (fn: (prev: LiveState) => LiveState) => void,
): () => void {
  const timers: ReturnType<typeof setInterval>[] = [];
  const view = mockState();

  if (view === "loading" || view === "error" || view === "empty") {
    const status: LiveStatus =
      view === "loading" ? "connecting" : view === "error" ? "offline" : "live";
    setState(() => ({
      ...emptyLiveState(),
      status,
      samples: view === "error" ? emptyLiveState().samples : flatSamples(0),
      bin: status === "live" ? { ...ON } : { ...OFF },
      phone: status === "live" ? { ...ON } : { ...OFF },
    }));
    return () => {};
  }

  const order = [102, 101, 103, 104];
  const seeded = fx.EVENTS[3] as EventSummary;
  const asking = fx.EVENTS[0] as EventSummary;
  const showAsk = askOpen();

  setState(() => ({
    status: "live",
    weight_g: BASELINE,
    samples: flatSamples(BASELINE),
    steps: [42, 78],
    tape: fx.EVENTS,
    ticket: showAsk
      ? { event: asking, phase: "weighing", arrival: 0 }
      : { event: seeded, phase: "identified", arrival: 0 },
    ask: showAsk ? fx.ASK : null,
    bin: { ...ON },
    phone: { ...ON },
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
        const event = (fx.EVENT_DETAILS[id] as { event: EventSummary }).event;
        index += 1;
        setState((prev) => {
          const last = prev.samples[prev.samples.length - 1] ?? BASELINE;
          const next = [...prev.samples.slice(1), last + (event.mass_g ?? 0)];
          return {
            ...prev,
            samples: next,
            weight_g: next[next.length - 1] ?? BASELINE,
            steps: [...prev.steps.slice(-4), next.length - 1],
            ticket: { event, phase: "weighing", arrival: (prev.ticket?.arrival ?? 0) + 1 },
            tape: [event, ...prev.tape.filter((e) => e.id !== event.id)],
          };
        });
        setTimeout(() => {
          setState((prev) =>
            prev.ticket && prev.ticket.event.id === id
              ? { ...prev, ticket: { ...prev.ticket, phase: "identified" } }
              : prev,
          );
        }, 700);
      }, 9000),
    );
  }

  return () => timers.forEach(clearInterval);
}
