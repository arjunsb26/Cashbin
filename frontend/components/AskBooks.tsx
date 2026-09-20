"use client";

import { useState } from "react";
import { useAsk } from "@/lib/api";
import type { AskResponse } from "@/lib/api";
import { Button, Field, Input, SectionTitle, Skeleton, cx } from "./ui";

/** Questions a judge would ask, offered as text that copies into the box for editing. */
const EXAMPLES: Record<"books" | "trends" | "review", string[]> = {
  review: [
    "What is waiting on me and how much money is in it?",
    "Which estimates look high against the catalog?",
    "What did the agent propose and why?",
  ],
  books: [
    "What did we write off this week and why?",
    "Which entries have a tax treatment different from the book one?",
    "What is still on the register and what is it worth?",
  ],
  trends: [
    "Where did most of the wasted money go this week?",
    "How much food did we throw out and what did it cost?",
    "What would we save by following the advice?",
  ],
};

/**
 * A question in plain words, answered from the books by an agent that looks
 * things up and shows what it looked at. The question is sent as data; the
 * answer comes back only from what the lookups returned.
 */
export function AskBooks({
  where,
  className,
}: {
  where: "books" | "trends" | "review";
  className?: string;
}) {
  const [typed, setTyped] = useState("");
  const [asked, setAsked] = useState("");
  const ask = useAsk();
  const answer: AskResponse | null = ask.data ?? null;
  const question = typed.trim().slice(0, 200);

  const submit = () => {
    if (!question) return;
    setAsked(question);
    ask.mutate(question);
  };

  return (
    <section className={cx("flex flex-col gap-3 border border-rule bg-surface p-4", className)}>
      <SectionTitle>Ask the books</SectionTitle>
      <p className="text-caption text-ink-soft">
        A question in your own words. The agent reads the journal, the register and the
        totals, then answers from what it found and shows you the lookups.
      </p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field label="Your question" htmlFor={"ask-" + where}>
          <Input
            id={"ask-" + where}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={EXAMPLES[where][0]}
            maxLength={200}
          />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button tone="primary" type="submit" loading={ask.isPending} disabled={!question}>
            Ask
          </Button>
          {EXAMPLES[where].map((example) => (
            <button
              key={example}
              type="button"
              className="text-left text-caption text-ink-soft underline decoration-rule underline-offset-2 hover:text-ink"
              onClick={() => setTyped(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </form>

      {ask.isPending ? (
        <div className="flex flex-col gap-2 pt-1" aria-live="polite">
          <p className="text-caption text-ink-soft">Looking through the books.</p>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ) : null}

      {ask.isError ? (
        <p className="text-body text-red-ink">
          {ask.error instanceof Error && ask.error.message
            ? ask.error.message
            : "The books did not answer. Try again in a moment."}
        </p>
      ) : null}

      {answer && !ask.isPending ? (
        <div className="flex flex-col gap-2 border-t border-rule pt-3" aria-live="polite">
          <p className="text-caption text-ink-soft">You asked: {asked}</p>
          <p className="text-body">{answer.answer}</p>
          {answer.steps.length > 0 ? (
            <details>
              <summary className="cursor-pointer text-caption text-ink-soft">
                How it got there, {answer.steps.length}{" "}
                {answer.steps.length === 1 ? "lookup" : "lookups"}
                {answer.latency_ms ? ", " + (answer.latency_ms / 1000).toFixed(1) + " s" : ""}
              </summary>
              <ol className="m-0 list-decimal pl-5 pt-2">
                {answer.steps.map((step, i) => (
                  <li key={i} className="py-1 text-caption">
                    <span className="text-ink">{stepWords(step.tool)}</span>
                    {step.args_summary ? (
                      <span className="text-ink-soft">, {step.args_summary}</span>
                    ) : null}
                    {step.finding ? <span className="block text-ink-soft">{step.finding}</span> : null}
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
          {!answer.grounded ? (
            <p className="text-caption text-caution">
              This answer could not be tied to a figure in the books, so treat it as words, not
              numbers.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** A tool's name in the words a person would use for the lookup. */
function stepWords(tool: string): string {
  const words: Record<string, string> = {
    journal_entries: "Read the journal",
    trial_balance: "Totalled the trial balance",
    register: "Looked at the register",
    stats: "Added up the period",
    recent_tickets: "Read recent tickets",
    close_latest: "Read the last close",
    rules: "Checked the rules",
    policy: "Checked the settings",
  };
  return words[tool] ?? tool.replace(/_/g, " ");
}
