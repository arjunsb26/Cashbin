// Which state a screen is asked to show. The query string picks it, so every
// state is reachable for review and for the screenshot run.
export type MockState = "populated" | "empty" | "loading" | "error";

function param(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

export function mockState(): MockState {
  const value = param("state");
  if (value === "empty" || value === "loading" || value === "error") return value;
  return "populated";
}

export function replayOn(): boolean {
  return param("replay") === "1";
}

export function askOpen(): boolean {
  return param("ask") === "1";
}
