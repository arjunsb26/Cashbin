// Builds the app in mock mode, starts it, and captures every route at both sizes
// in every state it can be in. Run with: pnpm screenshots
//
// The build has to happen here. NEXT_PUBLIC_API_MOCK is baked into the bundle when
// the app is compiled, so setting it on `next start` alone leaves the pages talking
// to a backend that is not there. This overwrites .next with a mock build.
import { spawn } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const PORT = 3123;
const BASE = `http://127.0.0.1:${PORT}`;
const OUT = join(process.cwd(), "screenshots");

const SIZES = [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "390x844", width: 390, height: 844 },
];

const SHOTS = [
  { name: "live-populated", path: "/" },
  { name: "live-empty", path: "/?state=empty" },
  { name: "live-loading", path: "/?state=loading" },
  { name: "live-error", path: "/?state=error" },
  { name: "live-ask", path: "/?ask=1" },
  { name: "trends-populated", path: "/trends" },
  { name: "trends-week", path: "/trends", click: "text=By week" },
  { name: "trends-empty", path: "/trends?state=empty" },
  { name: "trends-loading", path: "/trends?state=loading" },
  { name: "trends-error", path: "/trends?state=error" },
  { name: "review-populated", path: "/review" },
  { name: "review-note", path: "/review", click: "text=Reject" },
  { name: "review-empty", path: "/review?state=empty" },
  { name: "review-loading", path: "/review?state=loading" },
  { name: "review-error", path: "/review?state=error" },
  { name: "books-populated", path: "/books" },
  { name: "books-empty", path: "/books?state=empty" },
  { name: "books-loading", path: "/books?state=loading" },
  { name: "books-error", path: "/books?state=error" },
  { name: "books-register", path: "/books/register" },
  { name: "books-register-empty", path: "/books/register?state=empty" },
  { name: "books-register-loading", path: "/books/register?state=loading" },
  { name: "books-register-error", path: "/books/register?state=error" },
  { name: "books-register-add", path: "/books/register", click: "text=Add asset" },
  { name: "books-register-tags", path: "/books/register/tags" },
  { name: "books-trial-balance", path: "/books/trial-balance" },
  { name: "books-trial-balance-empty", path: "/books/trial-balance?state=empty" },
  { name: "books-trial-balance-error", path: "/books/trial-balance?state=error" },
  { name: "close-populated", path: "/close" },
  { name: "close-empty", path: "/close?state=empty" },
  { name: "close-loading", path: "/close?state=loading" },
  { name: "close-error", path: "/close?state=error" },
  { name: "settings-dialog", path: "/", click: 'button:has-text("Settings")' },
  { name: "event-populated", path: "/events/102" },
  { name: "event-loading", path: "/events/102?state=loading" },
  { name: "event-error", path: "/events/102?state=error" },
  { name: "event-ask", path: "/events/105" },
  { name: "event-journal-table", path: "/events/102", click: "text=Show the journal table" },
  {
    name: "evidence-drawer",
    path: "/",
    click: 'button[aria-label*="Open the evidence for ticket"]',
  },
  { name: "setup-populated", path: "/setup" },
  { name: "setup-empty", path: "/setup?state=empty" },
  { name: "kit", path: "/kit" },
];

function waitForServer(url, attempts = 90) {
  return new Promise((resolve, reject) => {
    const tick = async (left) => {
      try {
        const res = await fetch(url);
        if (res.ok) return resolve();
      } catch {
        // not up yet
      }
      if (left === 0) return reject(new Error("The app never came up."));
      setTimeout(() => tick(left - 1), 500);
    };
    void tick(attempts);
  });
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

function run(args) {
  return new Promise((resolve, reject) => {
    const child = spawn("node", ["node_modules/next/dist/bin/next", ...args], {
      env: { ...process.env, NEXT_PUBLIC_API_MOCK: "1" },
      stdio: "inherit",
      shell: false,
    });
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(new Error(`next ${args[0]} exited with ${code}`)),
    );
  });
}

console.log("Building in mock mode.");
await run(["build"]);

const server = spawn("node", ["node_modules/next/dist/bin/next", "start", "-p", String(PORT)], {
  env: { ...process.env, NEXT_PUBLIC_API_MOCK: "1" },
  stdio: "ignore",
  shell: false,
});

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
        await page.locator(shot.click).first().click();
        await page.waitForTimeout(400);
      }
      await page.waitForTimeout(shot.path.includes("loading") ? 600 : 900);
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
