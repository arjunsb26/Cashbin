"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as Tooltip from "@radix-ui/react-tooltip";
import { EvidenceDrawer } from "./EvidenceDrawer";

type EvidenceRequest = { eventId: number; focus: string };

type EvidenceApi = {
  open: (eventId: number, focus: string) => void;
  close: () => void;
  request: EvidenceRequest | null;
};

const EvidenceContext = createContext<EvidenceApi | null>(null);

export function useEvidence(): EvidenceApi {
  const api = useContext(EvidenceContext);
  if (!api) throw new Error("Evidence drawer used outside its provider.");
  return api;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          // One retry, because a read that lost a connection once is not an
          // outage, and an error panel that a reload would have cleared teaches
          // the room the wrong thing during a demo.
          queries: {
            retry: 1,
            retryDelay: 400,
            refetchOnWindowFocus: false,
            staleTime: 5000,
          },
        },
      }),
  );
  const [request, setRequest] = useState<EvidenceRequest | null>(null);

  const open = useCallback((eventId: number, focus: string) => {
    setRequest({ eventId, focus });
  }, []);
  const close = useCallback(() => setRequest(null), []);
  const api = useMemo(() => ({ open, close, request }), [open, close, request]);

  return (
    <QueryClientProvider client={client}>
      <Tooltip.Provider delayDuration={200}>
        <EvidenceContext.Provider value={api}>
          {children}
          <EvidenceDrawer />
        </EvidenceContext.Provider>
      </Tooltip.Provider>
    </QueryClientProvider>
  );
}
