"use client";

import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { FIRST_RUN_STEPS, FIRST_RUN_TITLE, SIMULATOR_COMMAND } from "@/lib/copy";
import { cx } from "./ui";

/**
 * What stands where the ticket goes before anything has been thrown away.
 *
 * An empty state that only says it is empty leaves a person looking for the
 * button. This one says the three things that have to happen, in order, and hands
 * over the command rather than asking anyone to retype it off a screen.
 */
export function FirstRun() {
  return (
    <div
      className="flex max-w-full flex-col gap-4 rounded-ticket border border-dashed border-rule bg-surface p-5 lg:p-6"
      style={{ width: "var(--ticket-w)" }}
    >
      <h2 className="text-section">{FIRST_RUN_TITLE}</h2>
      <ol className="m-0 flex list-none flex-col gap-2 p-0">
        {FIRST_RUN_STEPS.map((step, i) => (
          <li key={step} className="flex gap-3 text-body">
            <span className="text-ink-soft">{i + 1}.</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <CommandBox command={SIMULATOR_COMMAND} />
    </div>
  );
}

/**
 * The command, with a button that puts it on the clipboard. It wraps rather than
 * scrolling: a command box that hides its own second half is worse than two lines,
 * because someone reading from a metre away cannot tell there is more.
 */
function CommandBox({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  return (
    <div className="flex items-stretch gap-2">
      <pre className="m-0 min-w-0 flex-1 whitespace-pre-wrap break-words border border-rule bg-bar px-3 py-2 text-caption text-ink">
        {command}
      </pre>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard?.writeText(command).then(() => setCopied(true));
        }}
        className={cx(
          "inline-flex shrink-0 items-center gap-2 rounded-control border border-control-border bg-surface px-3 text-body",
          "transition-colors duration-fast ease-standard hover:bg-bar",
        )}
      >
        {copied ? (
          <Check size={16} strokeWidth={1.5} aria-hidden="true" />
        ) : (
          <Copy size={16} strokeWidth={1.5} aria-hidden="true" />
        )}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
