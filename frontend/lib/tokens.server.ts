import { readFileSync } from "node:fs";
import { join } from "node:path";

// The manifest and the theme colour need real values, not CSS variables.
// They are read out of app/tokens.css at build time so there is still one source.
const css = readFileSync(join(process.cwd(), "app", "tokens.css"), "utf8");

export function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match || !match[1]) throw new Error(`Token --${name} is not defined in app/tokens.css.`);
  return match[1].trim();
}
