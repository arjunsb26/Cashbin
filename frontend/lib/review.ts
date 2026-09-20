// The words above the review queue. Every wire shape comes from the contract.
//
// The queue's types used to be restated here, because the backend was being
// written as the screen was. They are in `contracts/api-types.ts` now and are
// re-exported from `lib/types.ts` with the rest, so nothing on this screen can
// drift from what the backend sends. What is left here is the grouping and the
// plain sentences, which are the dashboard's own and are on no wire.

import type { ReviewKind } from "./types";

/** The three groups the queue is read in, and the words above each one. */
export const REVIEW_GROUPS = [
  {
    id: "asks",
    title: "Open questions",
    blurb: "The bin could not tell what it was. Answer one and the ticket finishes itself.",
    kinds: ["unresolved_ask"] as ReviewKind[],
  },
  {
    id: "amounts",
    title: "Amounts to approve",
    blurb: "Postings a person should stand behind before they leave the books.",
    kinds: ["donation", "estimate_above_threshold", "confident_overruled"] as ReviewKind[],
  },
  {
    id: "register",
    title: "Equipment that was never on the register",
    blurb: "Worth enough to have been an asset, and the register has never heard of it.",
    kinds: ["possible_unrecorded_asset"] as ReviewKind[],
  },
] as const;

/** One plain sentence per reason, so a stranger knows why the row is there. */
export const REVIEW_KIND_WORDS: Record<ReviewKind, string> = {
  unresolved_ask: "Nobody answered the question",
  estimate_above_threshold: "Valued by a model, above the amount that needs a person",
  donation: "Claimed as a donation",
  possible_unrecorded_asset: "Looks like equipment that was never tagged",
  confident_overruled: "A person overruled what the bin was sure of",
};

export function reviewGroupOf(kind: ReviewKind): string {
  const group = REVIEW_GROUPS.find((g) => (g.kinds as ReviewKind[]).includes(kind));
  return group?.id ?? "amounts";
}

/** What the agent proposed, in the fewest words that are still true. */
export const PROPOSAL_WORDS: Record<"approve" | "reject" | "ask_person", string> = {
  approve: "The agent would approve this",
  reject: "The agent would reject this",
  ask_person: "The agent wants a person to decide",
};
