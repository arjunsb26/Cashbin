"use client";

import { useEffect, useState } from "react";
import type { AskView } from "@/lib/derive";
import { formatProbability, readLabel } from "@/lib/format";
import { imageSrc, useAnswerAsk } from "@/lib/api";
import { CropFrame } from "./CropFrame";
import { Button, Field, Input, cx } from "./ui";

/**
 * The ask takes over the ticket body. Keys 1 to 4 answer it.
 * Free text is read into a small object first, and the page shows what it understood.
 */
export function AskPanel({ ask }: { ask: AskView }) {
  const [answered, setAnswered] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);
  const [raw, setRaw] = useState("");
  const answer = useAnswerAsk();
  const read = readLabel(raw);

  const send = (label: string) => {
    setAnswered(label);
    answer.mutate({ event_id: ask.event_id, label, by: "person" });
  };

  useEffect(() => {
    if (answered) return;
    const onKey = (e: KeyboardEvent) => {
      if (typing) return;
      const index = Number(e.key) - 1;
      const candidate = ask.candidates[index];
      if (candidate) send(candidate.label);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (answered) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-section">{answered}</p>
        <p className="text-caption text-ink-soft">
          Learned. Next time this is recognised without asking.
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-4">
      <CropFrame
        src={imageSrc(ask.crop_url)}
        label="Crop of the item in question"
        size={120}
      />
      <div className="flex-1">
        <h3 className="text-section">Which is it?</h3>
        <ul className="m-0 flex list-none flex-col gap-2 p-0 pt-3">
          {ask.candidates.slice(0, 4).map((candidate, i) => (
            <li key={candidate.label}>
              <button
                type="button"
                onClick={() => send(candidate.label)}
                className="flex h-11 w-full items-center justify-between rounded-control border border-control-border bg-surface px-3 text-body transition-colors duration-fast ease-standard hover:bg-bar"
              >
                <span>
                  <span className="pr-2 text-ink-soft">{i + 1}</span>
                  {candidate.label}
                </span>
                <span className="text-caption text-ink-soft">
                  {formatProbability(candidate.p)}
                </span>
              </button>
            </li>
          ))}
        </ul>

        {typing ? (
          <div className="flex flex-col gap-2 pt-3">
            <Field
              label="What is it"
              hint="Up to 40 characters. Letters, digits, spaces and hyphens."
              htmlFor="ask-other"
            >
              <Input
                id="ask-other"
                autoFocus
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                placeholder="cable coil"
              />
            </Field>
            {raw.length > 0 ? (
              <p className={cx("text-caption", read.ok ? "text-ink-soft" : "text-red-ink")}>
                {read.ok
                  ? `Understood as "${read.label}".`
                  : "Nothing usable in that. Try letters and digits."}
                {read.dropped ? ` Left out: ${read.dropped}` : ""}
              </p>
            ) : null}
            <div className="flex gap-2">
              <Button tone="primary" disabled={!read.ok} onClick={() => send(read.label)}>
                Use this label
              </Button>
              <Button onClick={() => setTyping(false)}>Back to the candidates</Button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setTyping(true)}
            className="mt-3 text-body underline underline-offset-2"
          >
            Something else
          </button>
        )}
      </div>
    </div>
  );
}
