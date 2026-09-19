"use client";

import { useEffect, useState } from "react";
import { useLearned, useRounds, useSaveThresholds, useThresholds } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type { Thresholds } from "@/lib/types";
import { LearningChart } from "@/components/LearningChart";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "@/components/ui";

export default function LearningPage() {
  const rounds = useRounds();
  const learned = useLearned();

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Learning"
        description="Every correction is remembered. These are the rounds since the bin was switched on."
      />

      <section>
        {rounds.isPending ? <Skeleton className="h-[280px] w-full" /> : null}
        {rounds.isError ? (
          <ErrorState
            title="The rounds did not load. The backend is not answering."
            onRetry={() => rounds.refetch()}
          />
        ) : null}
        {rounds.data && rounds.data.length === 0 ? (
          <EmptyState title="No rounds yet. The first round opens with the first toss." />
        ) : null}
        {rounds.data && rounds.data.length > 0 ? (
          <>
            <LearningChart rounds={rounds.data} />
            <p className="pt-2 text-caption text-ink-soft">
              Cost per toss is on its own scale, which is why it is dashed.
            </p>
          </>
        ) : null}
      </section>

      <section className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div>
          <SectionTitle>What it learned</SectionTitle>
          {learned.isPending ? (
            <div className="flex flex-col gap-2 pt-3">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          ) : null}
          {learned.isError ? (
            <div className="pt-3">
              <ErrorState
                title="The corrections did not load. The backend is not answering."
                onRetry={() => learned.refetch()}
              />
            </div>
          ) : null}
          {learned.data && learned.data.length === 0 ? (
            <div className="pt-3">
              <EmptyState title="Nothing corrected yet. Answer an ask and it shows up here." />
            </div>
          ) : null}
          {learned.data && learned.data.length > 0 ? (
            <ul className="m-0 list-none p-0 pt-3">
              {learned.data.map((note) => (
                <li key={note.id} className="border-b border-rule py-2">
                  <p className="text-body">{note.text}</p>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <ThresholdForm />
      </section>
    </div>
  );
}

function ThresholdForm() {
  const thresholds = useThresholds();
  const save = useSaveThresholds();
  const [draft, setDraft] = useState<Thresholds | null>(null);

  useEffect(() => {
    if (thresholds.data && draft === null) setDraft(thresholds.data);
  }, [thresholds.data, draft]);

  return (
    <div>
      <SectionTitle>When it asks</SectionTitle>
      {thresholds.isPending || draft === null ? (
        <div className="flex flex-col gap-3 pt-3">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : (
        <div className="flex max-w-[320px] flex-col gap-4 pt-3">
          <Field
            label="Confident enough"
            hint={`Below this the system asks a person. Now at ${formatPercent(draft.confident_p)}.`}
            htmlFor="confident"
          >
            <Input
              id="confident"
              inputMode="decimal"
              value={draft.confident_p}
              onChange={(e) => setDraft({ ...draft, confident_p: Number(e.target.value) })}
            />
          </Field>
          <Field
            label="Margin over second place"
            hint="How far ahead the top answer has to be before it is accepted."
            htmlFor="margin"
          >
            <Input
              id="margin"
              inputMode="decimal"
              value={draft.min_margin}
              onChange={(e) => setDraft({ ...draft, min_margin: Number(e.target.value) })}
            />
          </Field>
          <Field
            label="Memory distance"
            hint="How close a remembered example has to be to count as the same thing."
            htmlFor="memory"
          >
            <Input
              id="memory"
              inputMode="decimal"
              value={draft.memory_max_dist}
              onChange={(e) => setDraft({ ...draft, memory_max_dist: Number(e.target.value) })}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Button tone="primary" loading={save.isPending} onClick={() => save.mutate(draft)}>
              Save thresholds
            </Button>
            {save.isSuccess ? <span className="text-caption text-kept">Saved.</span> : null}
          </div>
        </div>
      )}
    </div>
  );
}
