// Mock mode. Reached only through the flag switch in lib/api.ts.
// The query string picks the state a screen is in, so every state is reachable
// for review and for the screenshot run: ?state=empty, loading, error.
import * as fx from "./fixtures";
import { mockState } from "./state";
import type { StatsRange } from "../derive";
import type { ReviewListResponse, StatsResponse } from "../types";
import type {
  AssetRead,
  CloseRead,
  EventDetail,
  EventSummary,
  JournalResponse,
  RoundListResponse,
  RuleRead,
  SettingsRead,
  SummaryResponse,
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

const EMPTY_JOURNAL: JournalResponse = {
  basis: null,
  entries: [],
  trial_balance: [],
  balanced: true,
};

export const mockApi = {
  summary: (): Promise<SummaryResponse> =>
    respond(fx.SUMMARY, {
      saved_if_followed_cents: 0,
      kg_diverted: 0,
      events: 0,
      first_try_accuracy: null,
    }),
  events: (): Promise<EventSummary[]> => respond(fx.EVENTS, []),
  event: (id: number): Promise<EventDetail> => {
    const detail = fx.EVENT_DETAILS[id];
    if (!detail) return Promise.reject(new Error("No ticket with that number."));
    return respond(detail, detail);
  },
  journal: (): Promise<JournalResponse> => respond(fx.JOURNAL, EMPTY_JOURNAL),
  assets: (): Promise<AssetRead[]> => respond(fx.ASSETS, []),
  rounds: (): Promise<RoundListResponse> => respond(fx.ROUNDS, { rounds: [], learned: [] }),
  settings: (): Promise<SettingsRead> => respond(fx.SETTINGS, fx.SETTINGS),
  close: (): Promise<CloseRead | null> =>
    respond<CloseRead | null>({ ...fx.CLOSE, ...fx.CLOSE_BLOCKS }, null),
  setup: (): Promise<string[]> => respond(fx.SETUP, []),
  rules: (): Promise<RuleRead[]> => respond(fx.RULES, []),
  stats: (range: StatsRange): Promise<StatsResponse | null> =>
    respond<StatsResponse | null>(range === "week" ? fx.STATS_WEEK : fx.STATS_DAY, fx.STATS_NONE),
  review: (): Promise<ReviewListResponse | null> =>
    respond<ReviewListResponse | null>(fx.REVIEW, { items: [], open_count: 0 }),
};

export { startMockLive, emptyLiveState, flatSamples } from "./live";
export { mockState, replayOn, askOpen } from "./state";
export type { MockState } from "./state";
export { fx as fixtures };
