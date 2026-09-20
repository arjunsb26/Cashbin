"use client";

import { useSetup } from "@/lib/api";
import {
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  StatusDot,
} from "@/components/ui";

/** Not linked from the rail. It exists so nothing unfilled slips into a demo unnoticed. */
export default function SetupPage() {
  const setup = useSetup();
  const items = setup.data ?? [];

  return (
    <div className="max-w-[720px]">
      <PageHeader
        title="Still needs a person"
        description="One line for every seed value nobody has filled in yet. An empty page means the seed files are complete."
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

      {items.length > 0 ? (
        <ul className="m-0 list-none p-0">
          {items.map((item) => (
            <li key={item} className="flex gap-3 border-b border-rule py-3">
              <span className="pt-1">
                <StatusDot tone="caution" />
              </span>
              <p className="text-body">{item}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
