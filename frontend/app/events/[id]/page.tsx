"use client";

import { use } from "react";
import { useEvent } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import { EvidenceBody } from "@/components/EvidenceBody";
import { TAccounts } from "@/components/TAccounts";
import { Ticket } from "@/components/Ticket";
import { AskPanel } from "@/components/AskPanel";
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

  const difference =
    detail.event.item_class === "fixed_asset"
      ? "The books take the loss. The tax return already took it when the item was bought, which is why the tax side is smaller."
      : "Inventory cost flows through cost of goods sold, so there is no separate tax entry.";

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={detail.event.label ?? `Ticket ${detail.event.id}`}
        description={`Ticket ${detail.event.id}, ${formatDate(detail.event.created_at)} at ${formatTime(detail.event.created_at)}`}
      />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[560px_minmax(0,1fr)]">
        <div>
          <Ticket detail={detail} showMenu>
            {detail.ask ? <AskPanel ask={detail.ask} /> : undefined}
          </Ticket>
        </div>
        <div>
          {detail.evidence ? (
            <EvidenceBody evidence={detail.evidence} />
          ) : (
            <EmptyState title="No evidence yet. It fills in as soon as the label is final." />
          )}
        </div>
      </div>

      <TAccounts entries={detail.entries} difference={difference} />

      {detail.corrections.length > 0 ? (
        <section>
          <SectionTitle>Corrections</SectionTitle>
          <ul className="m-0 list-none p-0 pt-2">
            {detail.corrections.map((c) => (
              <li key={c.id} className="border-b border-rule py-2 text-body">
                {c.by} changed {c.field} from {c.old_value} to {c.new_value} at{" "}
                {formatTime(c.created_at)}.
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <FinanceFooter />
    </div>
  );
}
