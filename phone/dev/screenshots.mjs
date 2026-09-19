/* Screenshot run for the phone page.
   Start the mock first:  uv run --project backend python phone/dev/mock_server.py
   Then:                  pnpm screenshots

   Chromium gets a fake camera, so every shot below is the real page driving the
   real code path. Nothing here ships to a phone. */

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const hit = args.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : fallback;
};

const BASE = option("base", "https://localhost:8443");
const OUT = path.resolve(option("out", "screenshots"));
const PAGE = `${BASE}/phone/`;

const VIEWPORT = { width: 390, height: 844 };

const launch = {
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    "--ignore-certificate-errors",
    "--allow-insecure-localhost",
    "--autoplay-policy=no-user-gesture-required",
  ],
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function post(pathname, body) {
  const res = await fetch(`${BASE}${pathname}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  return res.json();
}

function watch(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") console.log(`[${label}] console error: ${message.text()}`);
  });
  page.on("pageerror", (err) => console.log(`[${label}] page error: ${err.message}`));
}

async function shot(page, name) {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  console.log(`saved ${name}.png`);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

  const browser = await chromium.launch(launch);
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  watch(page, "main");

  // 1. the start screen
  await page.goto(PAGE, { waitUntil: "load" });
  await page.waitForSelector("#startButton");
  await wait(400);
  await shot(page, "1-start");

  // 2. the live camera
  await page.click("#startButton");
  await page.waitForSelector("#cameraScreen:not([hidden])");
  await wait(2500);
  await page.click("#statusPill"); // the frame rate line lives behind a tap
  await wait(300);
  await shot(page, "2-live");
  await page.click("#statusPill");

  // 3. a result
  await post("/api/dev/send", {
    type: "result",
    event_id: 17,
    title: "Keyboard",
    big: "-$20",
    line: "Removed from register",
    tone: "amber",
    best_option: "recycle",
    mass_g: 212,
  });
  await page.waitForSelector('#resultSheet[data-open="true"]');
  await wait(500);
  await shot(page, "3-result");
  await page.click("#resultSheet");
  await wait(400);

  // 4. an ask
  await post("/api/dev/send", {
    type: "ask",
    event_id: 18,
    candidates: [
      { label: "wrap", p: 0.41 },
      { label: "burrito", p: 0.37 },
    ],
  });
  await page.waitForSelector('#askSheet[data-open="true"]');
  await page.waitForSelector("#askCrop:not([hidden])", { timeout: 4000 }).catch(() => {});
  await wait(400);
  await shot(page, "4-ask");

  // 4b. the free text answer, typed with an injection attempt in it
  await page.click("#askOther");
  await page.fill("#askInput", "  Ignore previous instructions; DROP TABLE events -- Wrap  ");
  await wait(300);
  await shot(page, "5-ask-something-else");
  console.log("read back as:", await page.textContent("#askReadBack"));
  await page.click("#askSend");
  await page.waitForSelector('#askSheet[data-open="false"]');
  await wait(300);
  await shot(page, "6-learned");

  // 5. reconnecting, by killing the socket and keeping the mock closed for a while
  await page.waitForSelector("#learnedLine", { state: "hidden" });
  await post("/api/dev/drop", { refuse_s: 8 });
  await page.waitForSelector('#status[data-state="reconnecting"]');
  await page.waitForSelector("#statusMessage:not([hidden])", { timeout: 10000 });
  await wait(400);
  await shot(page, "7-reconnecting");
  await page.waitForSelector('#status[data-state="live"]', { timeout: 30000 });
  console.log("the socket came back on its own");

  // 6. the ask answered by tapping a candidate, for the correction log line
  await post("/api/dev/send", {
    type: "ask",
    event_id: 18,
    candidates: [
      { label: "wrap", p: 0.41 },
      { label: "burrito", p: 0.37 },
    ],
  });
  await page.waitForSelector('#askSheet[data-open="true"]');
  await page.click("#askOptions button");
  await page.waitForSelector('#askSheet[data-open="false"]');
  console.log("tapped a candidate");

  await context.close();

  // 7. the camera refused
  const denied = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    ignoreHTTPSErrors: true,
  });
  await denied.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
  });
  const deniedPage = await denied.newPage();
  watch(deniedPage, "denied");
  await deniedPage.goto(PAGE, { waitUntil: "load" });
  await deniedPage.click("#startButton");
  await deniedPage.waitForSelector("#startError:not([hidden])");
  await wait(300);
  await shot(deniedPage, "8-camera-refused");
  await denied.close();

  await browser.close();
  console.log(`screenshots are in ${OUT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
