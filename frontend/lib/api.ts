"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { emptyLiveState, fixtures, mockApi, startMockLive } from "./mock";
import type {
  Asset,
  CloseReport,
  EventDetail,
  EventSummary,
  EvidenceBundle,
  JournalEntry,
  LearnedNote,
  NewAsset,
  Round,
  SetupItem,
  Summary,
  Thresholds,
  TrialBalanceRow,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://localhost:8443";
export const MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`The backend answered ${res.status} for ${path}.`);
  return (await res.json()) as T;
}

async function send<T>(path: string, method: "POST" | "PATCH", body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`The backend answered ${res.status} for ${path}.`);
  return (await res.json()) as T;
}

// The one seam between mock mode and the real backend.
const source = MOCK
  ? mockApi
  : {
      summary: () => get<Summary>("/api/summary"),
      events: () => get<EventSummary[]>("/api/events"),
      event: (id: number) => get<EventDetail>(`/api/events/${id}`),
      evidence: (id: number) => get<EvidenceBundle | null>(`/api/events/${id}/evidence`),
      journal: () => get<JournalEntry[]>("/api/journal"),
      trialBalance: () => get<TrialBalanceRow[]>("/api/journal/trial-balance"),
      assets: () => get<Asset[]>("/api/assets"),
      rounds: () => get<Round[]>("/api/metrics/rounds"),
      learned: () => get<LearnedNote[]>("/api/corrections"),
      thresholds: () => get<Thresholds>("/api/settings"),
      close: () => get<CloseReport | null>("/api/close/latest"),
      setup: () => get<SetupItem[]>("/api/setup"),
    };

/**
 * The mock lives behind this one switch. Nothing outside this file imports from
 * lib/mock, so a build without the flag has no mock data on any render path.
 * The screen sample data for /kit comes through here for the same reason.
 */
export const mockLive = MOCK ? startMockLive : null;
export const emptyLive = emptyLiveState;
export const sampleData = fixtures;

/**
 * Four of these paths are not in PLAN.md section 14 yet. They are what the
 * dashboard needs, and the backend lane has to serve them before the swap:
 * GET /api/events/{id}/evidence, GET /api/journal/trial-balance,
 * GET /api/close/latest, GET /api/setup.
 */
export const keys = {
  summary: ["summary"] as const,
  events: ["events"] as const,
  event: (id: number) => ["event", id] as const,
  evidence: (id: number) => ["evidence", id] as const,
  journal: ["journal"] as const,
  trialBalance: ["trial-balance"] as const,
  assets: ["assets"] as const,
  rounds: ["rounds"] as const,
  learned: ["learned"] as const,
  thresholds: ["thresholds"] as const,
  close: ["close"] as const,
  setup: ["setup"] as const,
};

export function useSummary() {
  return useQuery({ queryKey: keys.summary, queryFn: source.summary });
}

export function useEvents() {
  return useQuery({ queryKey: keys.events, queryFn: source.events });
}

export function useEvent(id: number) {
  return useQuery({ queryKey: keys.event(id), queryFn: () => source.event(id) });
}

export function useEvidenceQuery(id: number | null) {
  return useQuery({
    queryKey: keys.evidence(id ?? 0),
    queryFn: () => source.evidence(id as number),
    enabled: id !== null,
  });
}

export function useJournal() {
  return useQuery({ queryKey: keys.journal, queryFn: source.journal });
}

export function useTrialBalance() {
  return useQuery({ queryKey: keys.trialBalance, queryFn: source.trialBalance });
}

export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: source.assets });
}

export function useRounds() {
  return useQuery({ queryKey: keys.rounds, queryFn: source.rounds });
}

export function useLearned() {
  return useQuery({ queryKey: keys.learned, queryFn: source.learned });
}

export function useThresholds() {
  return useQuery({ queryKey: keys.thresholds, queryFn: source.thresholds });
}

export function useClose() {
  return useQuery({ queryKey: keys.close, queryFn: source.close });
}

export function useSetup() {
  return useQuery({ queryKey: keys.setup, queryFn: source.setup });
}

export function useAnswerAsk() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { event_id: number; label: string }) => {
      if (MOCK) return body;
      return send<{ event_id: number; label: string }>("/api/corrections", "POST", body);
    },
    onSuccess: (body) => {
      void client.invalidateQueries({ queryKey: keys.event(body.event_id) });
      void client.invalidateQueries({ queryKey: keys.events });
    },
  });
}

export function useAddAsset() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewAsset) => {
      if (MOCK) return body;
      return send<NewAsset>("/api/assets", "POST", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.assets });
    },
  });
}

export function useRunClose() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (MOCK) return null;
      return send<CloseReport>("/api/close", "POST", {});
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
      if (MOCK) return id;
      return send<{ id: number }>(`/api/events/${id}/void`, "POST", {});
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.events });
    },
  });
}

export function useSaveThresholds() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<Thresholds>) => {
      if (MOCK) return body;
      return send<Thresholds>("/api/settings", "PATCH", body);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.thresholds });
    },
  });
}
