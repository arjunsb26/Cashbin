// Mock mode. Reached only through the flag switch in lib/api.ts.
// The query string picks the state a screen is in, so every state is reachable
// for review and for the screenshot run: ?state=empty, loading, error.
import * as fx from "./fixtures";
import { mockState } from "./state";
import type {
  Asset,
  CloseReport,
  EventDetail,
  EventSummary,
  EvidenceBundle,
  JournalEntry,
  LearnedNote,
  Round,
  SetupItem,
  Summary,
  Thresholds,
  TrialBalanceRow,
} from "../types";

const NEVER = new Promise<never>(() => {});

async function respond<T>(value: T, empty: T): Promise<T> {
  const state = mockState();
  if (state === "loading") return NEVER;
  if (state === "error") throw new Error("The backend is not answering.");
  await new Promise((r) => setTimeout(r, 60));
  if (state === "empty") return empty;
  return value;
}

export const mockApi = {
  summary: (): Promise<Summary> =>
    respond(fx.SUMMARY, {
      saved_if_followed_cents: 0,
      kg_diverted: 0,
      n_events: 0,
      first_try_accuracy: 0,
      cheapest_equals_greenest: 0,
    }),
  events: (): Promise<EventSummary[]> => respond(fx.EVENTS, []),
  event: (id: number): Promise<EventDetail> => {
    const detail = fx.EVENT_DETAILS[id];
    if (!detail) return Promise.reject(new Error("No ticket with that number."));
    return respond(detail, detail);
  },
  evidence: (id: number): Promise<EvidenceBundle | null> => respond(fx.EVIDENCE[id] ?? null, null),
  journal: (): Promise<JournalEntry[]> => respond(fx.ENTRIES, []),
  trialBalance: (): Promise<TrialBalanceRow[]> => respond(fx.TRIAL_BALANCE, []),
  assets: (): Promise<Asset[]> => respond(fx.ASSETS, []),
  rounds: (): Promise<Round[]> => respond(fx.ROUNDS, []),
  learned: (): Promise<LearnedNote[]> => respond(fx.LEARNED, []),
  thresholds: (): Promise<Thresholds> => respond(fx.THRESHOLDS, fx.THRESHOLDS),
  close: (): Promise<CloseReport | null> => respond(fx.CLOSE, null),
  setup: (): Promise<SetupItem[]> => respond(fx.SETUP, []),
};

export { startMockLive, emptyLiveState, flatSamples } from "./live";
export { mockState, replayOn, askOpen } from "./state";
export type { MockState } from "./state";
export { fx as fixtures };
