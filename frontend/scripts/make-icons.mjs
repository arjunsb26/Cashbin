// Draws the app icon from the tokens: a bin outline with two ledger rules in it.
// Run with: node scripts/make-icons.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import sharp from "sharp";

const css = readFileSync(join(process.cwd(), "app", "tokens.css"), "utf8");
const token = (name) => {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`Token --${name} is missing.`);
  return match[1].trim();
};

const paper = token("paper");
const ink = token("ink");

const svg = (size) => `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="${paper}"/>
  <path d="M140 150 L372 150 L344 412 L168 412 Z" fill="none" stroke="${ink}" stroke-width="24" stroke-linejoin="round"/>
  <rect x="120" y="104" width="272" height="30" fill="${ink}"/>
  <rect x="186" y="228" width="140" height="18" fill="${ink}"/>
  <rect x="186" y="298" width="140" height="18" fill="${ink}"/>
</svg>`;

for (const size of [192, 512]) {
  const png = await sharp(Buffer.from(svg(size))).resize(size, size).png().toBuffer();
  writeFileSync(join(process.cwd(), "public", `icon-${size}.png`), png);
  console.log(`Wrote public/icon-${size}.png`);
}

writeFileSync(join(process.cwd(), "public", "icon.svg"), svg(512));
console.log("Wrote public/icon.svg");
