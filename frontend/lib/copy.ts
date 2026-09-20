// The sentences that explain a finance idea to someone who does not have one.
// They live here, in one file, so the ticket, the drawer, the register and the
// kit all say the same words and a change lands everywhere at once.

/** One plain sentence per term, shown on hover of the term wherever it appears. */
export const TERMS: Record<string, string> = {
  "book loss": "The value still sitting on the books the day the thing went in the bin, which comes off the register and lands in the profit and loss.",
  "tax basis": "What the thing is still worth for tax, which is often nothing, because the cost was already deducted in the year it was bought.",
  "waste expense": "What the item cost to buy, written off as waste because it was thrown away instead of sold or used.",
  "resale value": "What the thing would have fetched secondhand, which is the only number there is, because it was never on the books.",
  "book value": "What the books still say the thing is worth: what it cost, less the wear written off against it since.",
  "cost basis": "What the item cost to buy, which is the number the books write off when it is thrown away.",
  "fair market value": "What the thing would sell for today, secondhand and as it is.",
};

export function termFor(text: string): string | null {
  return TERMS[text.toLowerCase()] ?? null;
}

/**
 * Which of the three classes a ticket is, and why, in one line under the label.
 * The bin sorts everything into one of these three and the books treat each one
 * differently, so it is the first thing a person has to be told.
 */
export function classLine(
  itemClass: string | null | undefined,
  tag: string | null,
): string | null {
  if (itemClass === "inventory") return "Inventory, from the catalog";
  if (itemClass === "fixed_asset") {
    return tag ? `Fixed asset ${tag}, on your register` : "Fixed asset, on your register";
  }
  if (itemClass === "untracked") return "Not on your books, value estimated";
  return null;
}

/** The register's own sentence, on the page that is the register. */
export const REGISTER_LINE =
  "The register is your equipment with what it cost and when. Tag it so the bin recognises it.";

/** The first run, before anything has been tossed. */
export const FIRST_RUN_TITLE = "Nothing has been tossed yet";

export const FIRST_RUN_STEPS = [
  "Start the camera on the phone or the webcam.",
  "Toss something, or run the simulator.",
  "Every toss becomes a ticket here.",
];

/** The exact command, so it can be copied rather than retyped from a screen. */
export const SIMULATOR_COMMAND =
  "uv run --directory backend python ../sim/run_scenario.py --scenario demo --insecure";
