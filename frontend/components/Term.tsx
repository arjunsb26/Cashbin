"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import { termFor } from "@/lib/copy";

/**
 * A finance word with its one plain sentence on hover. The dotted underline is
 * there at rest, because a word that explains itself has to say so; the evidence
 * figure's dotted rule appears only on hover, so the two affordances stay apart.
 * The sentences live in lib/copy.ts and are never retyped into a screen.
 */
export function Term({ children }: { children: string }) {
  const explanation = termFor(children);
  if (!explanation) return <>{children}</>;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span className="cursor-help border-b border-dotted border-control-border">
          {children}
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          collisionPadding={12}
          className="max-w-[280px] rounded-control border border-rule bg-surface p-3 text-caption text-ink shadow-overlay"
        >
          {explanation}
          <Tooltip.Arrow className="fill-surface" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
