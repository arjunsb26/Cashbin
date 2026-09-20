"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import Link from "next/link";
import { useEvent } from "@/lib/api";
import { evidenceBundle } from "@/lib/derive";
import { useEvidence } from "./Providers";
import { EvidenceBody } from "./EvidenceBody";
import { Skeleton } from "./ui";

/** The one side panel in the product, because it has to sit beside the number it explains. */
export function EvidenceDrawer() {
  const { request, close } = useEvidence();
  const query = useEvent(request?.eventId ?? null);
  const evidence = query.data ? evidenceBundle(query.data) : null;

  return (
    <Dialog.Root open={request !== null} onOpenChange={(open) => (open ? null : close())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed right-0 top-0 flex h-full w-drawer max-w-full animate-drawer-in flex-col gap-4 overflow-y-auto border-l border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-title">
                {evidence ? evidence.title : "Where this number came from"}
              </Dialog.Title>
              {request ? (
                <p className="pt-1 text-caption text-ink-soft">
                  Ticket {request.eventId}, {request.focus}
                </p>
              ) : null}
            </div>
            <Dialog.Close
              className="rounded-control border border-control-border bg-surface p-1 text-ink-soft hover:bg-bar"
              aria-label="Close the evidence"
            >
              <X size={16} strokeWidth={1.5} />
            </Dialog.Close>
          </div>

          {query.isPending ? (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : null}

          {query.isError ? (
            <p className="border-l-2 border-red-ink pl-3 text-body">
              The evidence did not load. The backend is not answering.
            </p>
          ) : null}

          {evidence ? <EvidenceBody evidence={evidence} /> : null}

          {evidence ? (
            <Link
              className="mt-2 text-body underline underline-offset-2"
              href={`/events/${evidence.event_id}`}
              onClick={close}
            >
              Open the full ticket
            </Link>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
