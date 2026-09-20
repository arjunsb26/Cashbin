"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { emptyLiveState, fixtures, mockApi, startMockLive } from "./mock";
import { mediaSrc } from "./derive";
import type { StatsRange, StatsResponse } from "./derive";
import type {
  AssetCreate,
  AssetListResponse,
  AssetRead,
  CloseRead,
  CloseRequest,
  CorrectionCreate,
  CorrectionResponse,
  EventDetail,
  EventListResponse,
  EventSummary,
  JournalResponse,
  RoundListResponse,
  RoundRead,
  RulesResponse,
  SettingsRead,
  SettingsUpdate,
  SetupResponse,
  SummaryResponse,
  VoidResponse,
} from "./types";
import type { ReviewDecisionResponse, ReviewListResponse } from "./review";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://localhost:8443";
export const MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

/** Images come back as paths under the backend origin, so put the origin back on. */
export function imageSrc(url: string | null | undefined): string | null {
  return mediaSrc(API_URL, url);
}

class NotFound extends Error {}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: { accept: "application/json" } });
  if (res.status === 404) throw new NotFound(path);
  if (!res.ok) throw new Error(`The backend answered ${res.status} for ${path}.`);
  return (await res.json()) as T;
}

/** For the reads where nothing yet is an answer rather than a failure. */
async function getOrNull<T>(path: string): Promise<T | null> {
  try {
    return await get<T>(path);
  } catch (error) {
    if (error instanceof NotFound) return null;
    throw error;
  }
}

async function send<T>(path: string, method: "POST" | "PATCH", body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await refused(res, path);
  return (await res.json()) as T;
}

/**
 * The backend's own sentence, when it sent one.
 *
 * A refusal like "No camera frames yet. Start the camera first." is the whole
 * answer to what went wrong, and it is written for a person. Reaching for the
 * status code instead would throw that sentence away and print a number.
 */
export class Refused extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function refused(res: Response, path: string): Promise<Refused> {
  let sentence = "";
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") sentence = body.detail;
  } catch {
    // Not every refusal carries a body.
  }
  return new Refused(res.status, sentence || `The backend answered ${res.status} for ${path}.`);
}

// The one seam between mock mode and the real backend.
const source = MOCK
  ? mockApi
  : {
      summary: () => get<SummaryResponse>("/api/summary"),
      events: () =>
        get<EventListResponse>("/api/events").then((body) => body.events ?? []),
      event: (id: number) => get<EventDetail>(`/api/events/${id}`),
      journal: () => get<JournalResponse>("/api/journal"),
      assets: () => get<AssetListResponse>("/api/assets").then((body) => body.assets ?? []),
      rounds: () => get<RoundListResponse>("/api/metrics/rounds"),
      settings: () => get<SettingsRead>("/api/settings"),
      close: () => getOrNull<CloseRead>("/api/close/latest"),
      setup: () => get<SetupResponse>("/api/setup").then((body) => body.items ?? []),
      // A backend older than the rules route answers 404, and the drawer then
      // prints the rule's code on its own, as it did before the route existed.
      rules: () => getOrNull<RulesResponse>("/api/rules").then((body) => body?.rules ?? []),
      // Two routes newer than this screen. A backend without them answers 404, and
      // null is read as "not answering yet" rather than as an empty page, so
      // nobody is told there is no waste when nobody was asked.
      stats: (range: StatsRange) => getOrNull<StatsResponse>(`/api/stats?range=${range}`),
      review: () => getOrNull<ReviewListResponse>("/api/review"),
    };

/**
 * The mock lives behind this one switch. Nothing outside this file imports from
 * lib/mock, so a build without the flag has no mock data on any render path.
 * The screen sample data for /kit comes through here for the same reason.
 */
export const mockLive = MOCK ? startMockLive : null;
export const emptyLive = emptyLiveState;
export const sampleData = fixtures;

export const keys = {
  summary: ["summary"] as const,
  events: ["events"] as const,
  event: (id: number) => ["event", id] as const,
  journal: ["journal"] as const,
  assets: ["assets"] as const,
  rounds: ["rounds"] as const,
  settings: ["settings"] as const,
  close: ["close"] as const,
  setup: ["setup"] as const,
  rules: ["rules"] as const,
  stats: (range: StatsRange) => ["stats", range] as const,
  review: ["review"] as const,
  devTools: ["dev-tools"] as const,
};

/** The trends read, by day or by week. Null when the route is not there yet. */
export function useStats(range: StatsRange) {
  return useQuery({ queryKey: keys.stats(range), queryFn: () => source.stats(range) });
}

/** Everything a person still has to settle. Null when the route is not there yet. */
export function useReview() {
  return useQuery({ queryKey: keys.review, queryFn: source.review });
}

/**
 * A decision on one review item, applied on the screen before the backend has
 * answered and reconciled when it does. A refusal puts the row back as it was and
 * prints the backend's own sentence.
 */
export function useReviewDecision() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { id: number; decision: "approve" | "reject"; note: string }) => {
      if (MOCK) return null;
      return send<ReviewDecisionResponse>(`/api/review/${body.id}/${body.decision}`, "POST", {
        by: "person",
        note: body.note,
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.review });
      void client.invalidateQueries({ queryKey: keys.events });
      void client.invalidateQueries({ queryKey: keys.journal });
    },
  });
}

/** An answer to an open question, given from the queue instead of at the bin. */
export function useReviewAnswer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { id: number; label: string }) => {
      if (MOCK) return null;
      return send<CorrectionResponse>(`/api/review/${body.id}/answer`, "POST", {
        label: body.label,
        by: "person",
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.review });
      void client.invalidateQueries({ queryKey: keys.events });
    },
  });
}

export function useSummary() {
  return useQuery({ queryKey: keys.summary, queryFn: source.summary });
}

export function useEvents() {
  return useQuery({ queryKey: keys.events, queryFn: source.events });
}

export function useEvent(id: number | null) {
  return useQuery({
    queryKey: keys.event(id ?? 0),
    queryFn: () => source.event(id as number),
    enabled: id !== null,
  });
}

/**
 * The tape prints the amount that hit the books for every row, and that amount
 * only exists on the item record, so each row's ticket is read alongside the list.
 * They are small, local and cached, and the drawer and the event page then open
 * without a wait.
 */
export function useEventDetails(events: EventSummary[]) {
  const results = useQueries({
    queries: events.map((event) => ({
      queryKey: keys.event(event.id),
      queryFn: () => source.event(event.id),
      staleTime: 30_000,
    })),
  });
  const byId = new Map<number, EventDetail>();
  results.forEach((result, i) => {
    const event = events[i];
    if (event && result.data) byId.set(event.id, result.data);
  });
  return byId;
}

export function useJournal() {
  return useQuery({ queryKey: keys.journal, queryFn: source.journal });
}

export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: source.assets });
}

/**
 * The tag on a ticket's asset. The event read carries the asset id and not the
 * tag, and the line under a ticket's label has to name the tag a person can see
 * on the thing. It shares the register's own read, so it costs nothing extra.
 */
export function useAssetTag(assetId: number | null | undefined): string | null {
  const assets = useQuery({
    queryKey: keys.assets,
    queryFn: source.assets,
    enabled: assetId !== null && assetId !== undefined,
  });
  if (assetId === null || assetId === undefined) return null;
  return (assets.data ?? []).find((asset) => asset.id === assetId)?.tag ?? null;
}

export function useRounds() {
  return useQuery({ queryKey: keys.rounds, queryFn: source.rounds });
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: source.settings });
}

export function useClose() {
  return useQuery({ queryKey: keys.close, queryFn: source.close });
}

/** The rules in plain language, keyed by the code the engine cites. */
export function useRules() {
  return useQuery({ queryKey: keys.rules, queryFn: source.rules, staleTime: Infinity });
}

export function useSetup() {
  return useQuery({ queryKey: keys.setup, queryFn: source.setup });
}

/** One answer from a person. The label was read into a plain key before it got here. */
export function useAnswerAsk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: CorrectionCreate) => {
      if (MOCK) return { ...body, correction_id: 0, status: "confirmed" } as CorrectionResponse;
      return send<CorrectionResponse>("/api/corrections", "POST", body);
    },
    onSuccess: (body) => {
      void client.invalidateQueries({ queryKey: keys.event(body.event_id) });
      void client.invalidateQueries({ queryKey: keys.events });
      void client.invalidateQueries({ queryKey: keys.rounds });
    },
  });
}

/**
 * Whether this backend has its dev tools on.
 *
 * There is no flag to read, so the question is asked of the route itself: a backend
 * with the simulator mounted answers the empty body with a 422, one without it
 * answers 404 because the route is not there. Nothing is tossed either way. A
 * demo build talks to a backend with the tools off, so nothing shows.
 */
export function useDevTools() {
  return useQuery({
    queryKey: keys.devTools,
    queryFn: async () => {
      if (MOCK) return true;
      try {
        const res = await fetch(`${API_URL}/api/sim/expect`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: "{}",
        });
        return res.status !== 404;
      } catch {
        return false;
      }
    },
    staleTime: Infinity,
    retry: false,
  });
}

/** Dev only. One toss with a weight and whatever the camera is looking at. */
export function useAddToss() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { mass_g: number }) => {
      if (MOCK) return { event_id: 0, status: "detected" };
      return send<{ event_id: number; status: string }>("/api/sim/toss", "POST", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.events });
      void client.invalidateQueries({ queryKey: keys.summary });
    },
  });
}

export function useAddAsset() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: AssetCreate) => {
      if (MOCK) return null;
      return send<AssetRead>("/api/assets", "POST", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.assets });
    },
  });
}

export function useRunClose() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: CloseRequest) => {
      if (MOCK) return null;
      return send<CloseRead>("/api/close", "POST", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.close });
    },
  });
}

export function useVoidEvent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      if (MOCK) return { event_id: id, status: "void" } as VoidResponse;
      return send<VoidResponse>(`/api/events/${id}/void`, "POST", {});
    },
    onSuccess: (body) => {
      void client.invalidateQueries({ queryKey: keys.event(body.event_id) });
      void client.invalidateQueries({ queryKey: keys.events });
      void client.invalidateQueries({ queryKey: keys.journal });
    },
  });
}

export function useSaveSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: SettingsUpdate) => {
      if (MOCK) return null;
      return send<SettingsRead>("/api/settings", "PATCH", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.settings });
    },
  });
}

export function useStartRound() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (MOCK) return null;
      return send<RoundRead>("/api/metrics/rounds/start", "POST", {});
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.rounds });
      void client.invalidateQueries({ queryKey: keys.summary });
    },
  });
}
