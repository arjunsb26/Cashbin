// The review queue's shapes, until contracts carries them.
//
// Lane P's backend is written and its generated types land on main within the
// hour. These are the same fields, read as optional on the way in, so the screen
// draws whatever the backend actually sends and a missing field is a blank cell
// rather than a crash. Swap the import for the contract type when it arrives.

/** Why a ticket landed in the queue. PLAN.md 21a item 39. */
export type ReviewKind =
  | "donation"
  | "estimate_above_threshold"
  | "possible_unrecorded_asset"
  | "unresolved_ask"
  | "confident_overruled";

export type ReviewStatus = "open" | "approved" | "rejected";

export type ReviewItemRead = {
  id: number;
  event_id: number;
  kind: ReviewKind;
  status: ReviewStatus;
  label?: string | null;
  reason?: string;
  amount_cents?: number;
  asset_id?: number | null;
  asset_tag?: string | null;
  candidates?: { label: string; p: number }[];
  created_at?: string;
  decided_at?: string | null;
  decided_by?: string | null;
  note?: string | null;
};

export type ReviewListResponse = {
  items?: ReviewItemRead[];
  open_count?: number;
};

export type ReviewDecisionResponse = {
  item: ReviewItemRead;
  reversing_entry_ids?: number[];
  difference_cents?: number;
  detail?: string;
};

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
