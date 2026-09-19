// Fails when a raw colour literal appears outside app/tokens.css.
// DESIGN.md section 2: tokens live in one file and nowhere else.
import { readdir, readFile } from "node:fs/promises";
import { join, relative, sep } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const allowFiles = new Set(["app" + sep + "tokens.css"]);
const skipDirs = new Set(["node_modules", ".next", "screenshots", "public", "app" + sep + "fonts"]);
const exts = [".ts", ".tsx", ".css", ".mjs", ".js", ".json"];

const hex = /#[0-9a-fA-F]{3,8}\b/;
const rgb = /\brgba?\(/;

async function walk(dir, found) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(dir, entry.name);
    const rel = relative(root, full);
    if (entry.isDirectory()) {
      if (skipDirs.has(entry.name) || skipDirs.has(rel)) continue;
      await walk(full, found);
      continue;
    }
    if (!exts.some((e) => entry.name.endsWith(e))) continue;
    if (allowFiles.has(rel)) continue;
    const text = await readFile(full, "utf8");
    text.split("\n").forEach((line, i) => {
      if (line.includes("check-hex")) return;
      if (hex.test(line) || rgb.test(line)) {
        found.push(`${rel}:${i + 1}: ${line.trim()}`);
      }
    });
  }
}

const found = [];
await walk(root, found);

if (found.length > 0) {
  console.error("Raw colour values outside app/tokens.css:");
  for (const line of found) console.error("  " + line);
  process.exit(1);
}
console.log("No raw colour values outside app/tokens.css.");
