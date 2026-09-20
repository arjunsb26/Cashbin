"use client";

import { useEffect, useRef, useState } from "react";
import type { AskView } from "@/lib/derive";
import { formatProbability, readLabel } from "@/lib/format";
import { fromEditable } from "@/lib/keys";
import { imageSrc, useAnswerAsk } from "@/lib/api";
import { CropFrame } from "./CropFrame";
import { Button, Field, Input, cx } from "./ui";

/**
 * What a person has half typed, kept outside the component and keyed by ticket.
 *
 * The Live page redraws ten times a second off the scale, and a newer ask takes the
 * sheet from an older one. Either can take this panel off the screen and put it back,
 * and React state goes with it. Someone in the middle of a word would watch the box
 * empty itself. The draft outlives the panel, so it comes back as it was.
 */
const drafts = new Map<number, { typing: boolean; raw: string }>();

/**
 * The ask takes over the ticket body. Keys 1 to 4 answer it.
 * Free text is read into a small object first, and the page shows what it understood.
 */
export function AskPanel({ ask, onDismiss }: { ask: AskView; onDismiss: () => void }) {
  const draft = drafts.get(ask.event_id) ?? { typing: false, raw: "" };
  const [answered, setAnswered] = useState<string | null>(null);
  const [typing, setTypingState] = useState(draft.typing);
  const [raw, setRawState] = useState(draft.raw);
  const box = useRef<HTMLInputElement | null>(null);
  const answer = useAnswerAsk();
  const read = readLabel(raw);

  const setTyping = (next: boolean) => {
    drafts.set(ask.event_id, { typing: next, raw });
    setTypingState(next);
  };
  const setRaw = (next: string) => {
    drafts.set(ask.event_id, { typing, raw: next });
    setRawState(next);
  };

  const send = (label: string) => {
    drafts.delete(ask.event_id);
    setAnswered(label);
    answer.mutate({ event_id: ask.event_id, label, by: "person" });
  };

  // The box is revealed by a click, and a click leaves the focus on the button that
  // was clicked. Put it in the box, every time the box appears, so the next keystroke
  // lands where the person is looking.
  useEffect(() => {
    if (typing) box.current?.focus();
  }, [typing]);

  useEffect(() => {
    if (answered) return;
    const onKey = (e: KeyboardEvent) => {
      // Escape is the way out of a question, from the box as much as anywhere else.
      // It is not a character, so no one loses a keystroke to it.
      if (e.key === "Escape") {
        onDismiss();
        return;
      }
      // A digit typed into the label box is part of the label, never an answer.
      if (typing || fromEditable(e.target)) return;
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
        {ask.description ? (
          <p className="pt-1 text-caption text-ink-soft">Looks like: {ask.description}</p>
        ) : null}
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
                ref={box}
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
            className="mt-3 block text-body underline underline-offset-2"
          >
            Something else
          </button>
        )}

        {/* The way out. Nothing is posted and nothing is decided: the ticket stays
            in the tape marked asking, so the close still counts it as one that
            needed a person, and the screen moves on to whatever landed next. */}
        <button
          type="button"
          onClick={onDismiss}
          className="mt-3 block text-caption text-ink-soft underline underline-offset-2"
        >
          Not now
        </button>
      </div>
    </div>
  );
}
