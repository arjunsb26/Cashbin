// Fails when the product name is spelled out anywhere under /frontend.
// The name lives in /brand.json at the repo root and reaches the pages through
// lib/brand.ts, so renaming the product is one edit to one file.
import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const brand = JSON.parse(await readFile(join(root, "..", "brand.json"), "utf8"));
const names = [brand.name, brand.short_name]
  .filter((n) => typeof n === "string" && n.length > 2)
  .map((n) => n.toLowerCase());

const skipDirs = new Set(["node_modules", ".next", "screenshots", "test-results"]);
const skipFiles = new Set(["pnpm-lock.yaml", "scripts" + sep + "check-brand.mjs"]);
const exts = [".ts", ".tsx", ".css", ".mjs", ".js", ".json", ".md", ".html"];

async function walk(dir, found) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    const rel = relative(root, full);
    if (entry.isDirectory()) {
      if (skipDirs.has(entry.name)) continue;
      await walk(full, found);
      continue;
    }
    if (skipFiles.has(rel)) continue;
    if (!exts.some((e) => entry.name.endsWith(e))) continue;
    const text = (await readFile(full, "utf8")).toLowerCase();
    text.split("\n").forEach((line, i) => {
      if (names.some((name) => line.includes(name))) {
        found.push(`${rel}:${i + 1}: ${line.trim()}`);
      }
    });
  }
}

const found = [];
await walk(root, found);

if (found.length > 0) {
  console.error("The product name is written out under /frontend. Import lib/brand instead:");
  for (const line of found) console.error("  " + line);
  process.exit(1);
}
console.log("The product name appears nowhere under /frontend.");
