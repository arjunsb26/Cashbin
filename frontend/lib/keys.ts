/**
 * The one rule every window level shortcut obeys.
 *
 * The Live page answers an ask on 1 to 4, moves the tape on j and k, opens a ticket
 * on Enter and the evidence on e. All of those are letters and digits a person also
 * types into a box. A handler bound to the window sees the keystroke first, so
 * every one of them has to stand aside while the person is writing.
 */
export function fromEditable(target: EventTarget | null): boolean {
  if (!target || typeof target !== "object") return false;
  const node = target as { tagName?: unknown; isContentEditable?: unknown };
  const tag = typeof node.tagName === "string" ? node.tagName.toUpperCase() : "";
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return node.isContentEditable === true;
}
