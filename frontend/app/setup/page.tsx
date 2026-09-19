"use client";

import { useSetup } from "@/lib/api";
import {
  EmptyState,
  ErrorState,
  PageHeader,
  SectionTitle,
  Skeleton,
  StatusDot,
} from "@/components/ui";

/** Not linked from the rail. It exists so nothing unfilled slips into a demo unnoticed. */
export default function SetupPage() {
  const setup = useSetup();
  const items = setup.data ?? [];
  const waiting = items.filter((i) => !i.done);
  const done = items.filter((i) => i.done);

  return (
    <div className="max-w-[720px]">
      <PageHeader
        title="Still needs a person"
      />

      {setup.isPending ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-row w-full" />
          <Skeleton className="h-row w-full" />
        </div>
      ) : null}

      {setup.isError ? (
        <ErrorState
          title="The checklist did not load. The backend is not answering."
          onRetry={() => setup.refetch()}
        />
      ) : null}

      {setup.data && items.length === 0 ? (
        <EmptyState title="Nothing is waiting. Every seed value has been filled in." />
      ) : null}

      {waiting.length > 0 ? (
        <section className="pb-8">
          <SectionTitle>Waiting</SectionTitle>
          <ul className="m-0 list-none p-0 pt-2">
            {waiting.map((item) => (
              <li key={item.id} className="flex gap-3 border-b border-rule py-3">
                <span className="pt-1">
                  <StatusDot tone="caution" />
                </span>
                <div>
                  <p className="text-body">{item.what}</p>
                  <p className="text-caption text-ink-soft">
                    {item.file}, field {item.field}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {done.length > 0 ? (
        <section>
          <SectionTitle>Filled in</SectionTitle>
          <ul className="m-0 list-none p-0 pt-2">
            {done.map((item) => (
              <li key={item.id} className="flex gap-3 border-b border-rule py-3">
                <span className="pt-1">
                  <StatusDot tone="kept" />
                </span>
                <div>
                  <p className="text-body">{item.what}</p>
                  <p className="text-caption text-ink-soft">
                    {item.file}, field {item.field}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
