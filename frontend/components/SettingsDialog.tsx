"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Settings } from "lucide-react";
import { useSaveSettings, useSettings } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type { SettingsRead } from "@/lib/types";
import { Button, ErrorState, Field, Input, Skeleton, cx } from "./ui";

type Draft = Pick<SettingsRead, "confident_p" | "min_margin" | "memory_max_dist" | "tone_co2e_kg">;

/**
 * The thresholds, in a dialog off the foot of the rail.
 *
 * They used to sit on a page of their own, which put a form nobody touches beside
 * the numbers everybody reads. They are a setting, so they live where settings
 * live: one step away from every screen and in the way of none of them.
 */
export function SettingsDialog() {
  const [open, setOpen] = useState(false);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger
        className={cx(
          "flex flex-col items-center gap-1 border-l-2 border-l-transparent py-2 text-caption text-ink-soft",
          "transition-colors duration-fast ease-standard hover:bg-bar",
        )}
      >
        <Settings size={16} strokeWidth={1.5} aria-hidden="true" />
        Settings
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 max-h-[calc(100dvh-32px)] w-[440px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-control border border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
        >
          <Dialog.Title className="text-title">When the bin asks</Dialog.Title>
          <p className="pb-4 pt-1 text-caption text-ink-soft">
            How sure the bin has to be before it settles a ticket on its own.
          </p>
          <ThresholdForm onDone={() => setOpen(false)} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ThresholdForm({ onDone }: { onDone: () => void }) {
  const settings = useSettings();
  const save = useSaveSettings();
  const [draft, setDraft] = useState<Draft | null>(null);

  useEffect(() => {
    if (settings.data && draft === null) {
      setDraft({
        confident_p: settings.data.confident_p,
        min_margin: settings.data.min_margin,
        memory_max_dist: settings.data.memory_max_dist,
        tone_co2e_kg: settings.data.tone_co2e_kg,
      });
    }
  }, [settings.data, draft]);

  if (settings.isError) {
    return (
      <ErrorState
        title="The thresholds did not load. The backend is not answering."
        onRetry={() => settings.refetch()}
      />
    );
  }

  if (settings.isPending || draft === null) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Field
        label="Confident enough"
        hint={"Below this the bin asks a person. Now at " + formatPercent(draft.confident_p) + "."}
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
      <Field
        label="Carbon that counts as a difference"
        hint="A better option under this much CO2e still reads as green on the bin."
        htmlFor="carbon"
      >
        <Input
          id="carbon"
          inputMode="decimal"
          value={draft.tone_co2e_kg}
          onChange={(e) => setDraft({ ...draft, tone_co2e_kg: Number(e.target.value) })}
        />
      </Field>
      <div className="flex justify-end gap-2 pt-1">
        <Dialog.Close asChild>
          <Button>Cancel</Button>
        </Dialog.Close>
        <Button
          tone="primary"
          loading={save.isPending}
          onClick={() => save.mutate(draft, { onSuccess: onDone })}
        >
          Save thresholds
        </Button>
      </div>
      {save.isError ? (
        <p className="text-caption text-red-ink">
          The thresholds were not saved. The backend is not answering.
        </p>
      ) : null}
    </div>
  );
}
