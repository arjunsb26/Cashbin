import test from "node:test";
import assert from "node:assert/strict";

import { fromEditable } from "./keys.ts";

/** The handlers are given a real event target; a plain object stands in for one here. */
function target(props: { tagName?: string; isContentEditable?: boolean }): EventTarget {
  return props as unknown as EventTarget;
}

test("a keystroke in a text box belongs to the box, not to the shortcuts", () => {
  assert.equal(fromEditable(target({ tagName: "INPUT" })), true);
  assert.equal(fromEditable(target({ tagName: "input" })), true);
  assert.equal(fromEditable(target({ tagName: "TEXTAREA" })), true);
  assert.equal(fromEditable(target({ tagName: "SELECT" })), true);
  assert.equal(fromEditable(target({ tagName: "DIV", isContentEditable: true })), true);
});

test("a keystroke anywhere else reaches the shortcuts", () => {
  assert.equal(fromEditable(target({ tagName: "BODY" })), false);
  assert.equal(fromEditable(target({ tagName: "BUTTON" })), false);
  assert.equal(fromEditable(target({ tagName: "DIV", isContentEditable: false })), false);
  assert.equal(fromEditable(null), false);
});
