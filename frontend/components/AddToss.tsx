"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Refused, useAddToss, useDevTools } from "@/lib/api";
import { Button, Field, Input } from "./ui";

const DEFAULT_MASS_G = 150;

/**
 * A toss without a bin.
 *
 * The scale is the real way in, and on a laptop with no bin plugged in there is no
 * way in at all. This gives one: a weight, and whatever the camera is looking at
 * right now. It is a dev tool, so it is not rendered at all unless the backend has
 * its dev tools on, and the demo build talks to one that does not.
 */
export function AddToss() {
  const dev = useDevTools();
  const [open, setOpen] = useState(false);
  const [grams, setGrams] = useState(String(DEFAULT_MASS_G));
  const [refusal, setRefusal] = useState<string | null>(null);
  const toss = useAddToss();

  if (dev.data !== true) return null;

  const mass = Number(grams);
  const ok = Number.isFinite(mass) && mass > 0;

  const submit = () => {
    if (!ok || toss.isPending) return;
    setRefusal(null);
    toss.mutate(
      { mass_g: mass },
      {
        onSuccess: () => {
          setOpen(false);
          setGrams(String(DEFAULT_MASS_G));
        },
        onError: (error) =>
          setRefusal(
            error instanceof Refused
              ? error.message
              : "The toss did not go through. The backend is not answering.",
          ),
      },
    );
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setRefusal(null);
      }}
    >
      <Dialog.Trigger asChild>
        <Button tone="primary">Measure</Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-[var(--scrim)]" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 w-[420px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 rounded-control border border-rule bg-surface p-5 shadow-overlay"
          aria-describedby={undefined}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              submit();
            }
          }}
        >
          <Dialog.Title className="text-title">Measure</Dialog.Title>
          <div className="pt-4">
            <Field
              label="Weight"
              hint="About how much it weighs. The camera frame from right now is the photo."
              htmlFor="toss-mass"
            >
              <Input
                id="toss-mass"
                type="number"
                inputMode="numeric"
                min={1}
                autoFocus
                value={grams}
                onChange={(e) => setGrams(e.target.value)}
              />
            </Field>
            <p className="pt-1 text-caption text-ink-soft">Grams.</p>
          </div>
          {refusal ? <p className="pt-3 text-caption text-red-ink">{refusal}</p> : null}
          <div className="flex justify-end gap-2 pt-5">
            <Dialog.Close asChild>
              <Button>Cancel</Button>
            </Dialog.Close>
            <Button tone="primary" disabled={!ok} loading={toss.isPending} onClick={submit}>
              Add
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
