// Captures every tab against a real backend, at both sizes. Run with:
//
//   node scripts/screenshots-real.mjs --api http://127.0.0.1:9000 --out ../briefs/reports/lane-d/part5
//
// The sibling script, screenshots.mjs, photographs the mock and every state a
// screen can be in. This one photographs one real run: whatever the backend
// actually has in it, through the same components and the same formatting.
//
// The build has to happen here for the same reason it does there. NEXT_PUBLIC_*
// is baked into the bundle when the app is compiled, so pointing `next start` at
// a backend after the fact leaves the pages talking to whatever was compiled in.
import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import { chromium } from "@playwright/test";

function arg(name, fallback) {
  const at = process.argv.indexOf("--" + name);
  return at === -1 ? fallback : process.argv[at + 1];
}

const API = arg("api", "http://127.0.0.1:9000");
const PORT = Number(arg("port", "3001"));
const rawOut = arg("out", "screenshots-real");
const OUT = isAbsolute(rawOut) ? rawOut : resolve(process.cwd(), rawOut);
const BASE = `http://127.0.0.1:${PORT}`;

const SIZES = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "390x844", width: 390, height: 844 },
];

const SHOTS = [
  { name: "live", path: "/" },
  { name: "trends-day", path: "/trends" },
  { name: "trends-week", path: "/trends", click: "text=By week" },
  { name: "review", path: "/review" },
  { name: "review-working", path: "/review", click: "text=/^Looked at /" },
  { name: "review-note", path: "/review", click: 'button:has-text("Reject")' },
  { name: "books-journal", path: "/books" },
  { name: "books-register", path: "/books/register" },
  { name: "books-trial-balance", path: "/books/trial-balance" },
  { name: "close", path: "/close" },
  { name: "close-how-it-looked", path: "/close", click: "text=/^How it looked/" },
  { name: "event", path: "/events/2" },
  { name: "event-ask", path: "/events/5" },
];

const env = {
  ...process.env,
  NEXT_PUBLIC_API_URL: API,
  NEXT_PUBLIC_API_MOCK: "0",
};

function run(args) {
  return new Promise((ok, no) => {
    const child = spawn("node", ["node_modules/next/dist/bin/next", ...args], {
      env,
      stdio: "inherit",
      shell: false,
    });
    child.on("exit", (code) =>
      code === 0 ? ok() : no(new Error(`next ${args[0]} exited with ${code}`)),
    );
  });
}

function waitForServer(url, attempts = 120) {
  return new Promise((ok, no) => {
    const tick = async (left) => {
      try {
        const res = await fetch(url);
        if (res.ok) return ok();
      } catch {
        // not up yet
      }
      if (left === 0) return no(new Error("The app never came up."));
      setTimeout(() => tick(left - 1), 500);
    };
    void tick(attempts);
  });
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

console.log(`Building against ${API}.`);
await run(["build"]);

const server = spawn(
  "node",
  ["node_modules/next/dist/bin/next", "start", "-p", String(PORT)],
  { env, stdio: "ignore", shell: false },
);

const missed = [];
try {
  await waitForServer(BASE);
  const browser = await chromium.launch();
  for (const size of SIZES) {
    const context = await browser.newContext({
      viewport: { width: size.width, height: size.height },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    for (const shot of SHOTS) {
      await page.goto(BASE + shot.path, { waitUntil: "networkidle" });
      if (shot.click) {
        const target = page.locator(shot.click).first();
        if ((await target.count()) === 0) {
          missed.push(`${shot.name} ${size.name}: nothing matched ${shot.click}`);
          continue;
        }
        await target.click();
        await page.waitForTimeout(400);
      }
      await page.waitForTimeout(1200);
      await page.screenshot({
        path: join(OUT, `${shot.name}-${size.name}.png`),
        fullPage: !shot.click,
      });
      console.log(`${shot.name} ${size.name}`);
    }
    await context.close();
  }
  await browser.close();
} finally {
  server.kill();
}

if (missed.length > 0) {
  console.log("\nNot photographed, because the page had nothing to click:");
  for (const line of missed) console.log("  " + line);
}
