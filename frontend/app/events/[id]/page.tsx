"use client";

import { use } from "react";
import { useEvent, useJournal } from "@/lib/api";
import { accountNames, bookVsTax, evidenceBundle } from "@/lib/derive";
import { formatDate, formatTime } from "@/lib/format";
import { EvidenceBody } from "@/components/EvidenceBody";
import { TAccounts } from "@/components/TAccounts";
import { Ticket } from "@/components/Ticket";
import {
  EmptyState,
  ErrorState,
  FinanceFooter,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function EventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const event = useEvent(Number(id));
  const journal = useJournal();
  const names = accountNames(journal.data?.entries);

  if (event.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-7 w-48" />
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[560px_minmax(0,1fr)]">
          <Skeleton className="h-[420px] w-full" />
          <Skeleton className="h-[420px] w-full" />
        </div>
      </div>
    );
  }

  if (event.isError) {
    return (
      <ErrorState
        title="That ticket did not load. The backend is not answering."
        onRetry={() => event.refetch()}
      />
    );
  }

  const detail = event.data;
  if (!detail) {
    return <EmptyState title="No ticket with that number. Open one from the tape." />;
  }

  const evidence = evidenceBundle(detail);
  const corrections = detail.corrections ?? [];
  const phase = detail.event.label ? "identified" : "weighing";

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={detail.event.label ?? `Ticket ${detail.event.id}`}
        description={`Ticket ${detail.event.id}, ${formatDate(detail.event.created_at)} at ${formatTime(detail.event.created_at)}`}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[560px_minmax(0,1fr)]">
        <div>
          <Ticket event={detail.event} detail={detail} phase={phase} showMenu />
        </div>
        <div>
          <EvidenceBody evidence={evidence} />
        </div>
      </div>

      <TAccounts
        entries={detail.entries ?? []}
        difference={bookVsTax(detail.item_record?.class ?? detail.event.class)}
        names={names}
      />

      {corrections.length > 0 ? (
        <section>
          <SectionTitle>Corrections</SectionTitle>
          <ul className="m-0 list-none p-0 pt-2">
            {corrections.map((c) => (
              <li key={c.id} className="border-b border-rule py-2 text-body">
                {c.by} changed {c.field} from {c.old_value ?? "nothing"} to{" "}
                {c.new_value ?? "nothing"} at {formatTime(c.created_at)}.
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <FinanceFooter />
    </div>
  );
}
