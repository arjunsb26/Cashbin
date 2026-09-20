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

const BASE = option("base", "https://localhost:8444");
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

async function get(pathname) {
  const res = await fetch(`${BASE}${pathname}`);
  return res.json();
}

const chaos = (step) => post("/api/dev/chaos", { step });

// Every move through the page's state machine, kept so the run can print the
// whole story at the end.
const transitions = [];

function watch(page, label) {
  page.on("console", (message) => {
    const line = message.text();
    if (line.startsWith("sheet:") || line.startsWith("socket:")) transitions.push(line);
    if (message.type() === "error") console.log(`[${label}] console error: ${line}`);
  });
  page.on("pageerror", (err) => console.log(`[${label}] page error: ${err.message}`));
}

/* ---- what the screen must say after a step ---- */

async function is(page, selector, expected) {
  const found = (await page.textContent(selector))?.trim();
  if (found !== expected) throw new Error(`${selector} reads "${found}", not "${expected}"`);
  console.log(`${selector} reads "${expected}"`);
}

async function hidden(page, selector, what) {
  if (!(await page.isHidden(selector))) throw new Error(`${what} is on the screen and should not be`);
  console.log(`${what} is off the screen`);
}

async function open(page, selector, expected, what) {
  const found = (await page.getAttribute(selector, "data-open")) === "true";
  if (found !== expected) {
    throw new Error(`${what} is ${found ? "open" : "closed"} and should be ${expected ? "open" : "closed"}`);
  }
  console.log(`${what} is ${expected ? "open" : "closed"}`);
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

  // The run drives every message itself, so the mock's own scripted result and
  // ask are turned off first and each shot comes out the same every time.
  await post("/api/dev/script", { on: false });

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

  // 2b. adding a toss by hand, the control the backend only offers with its dev
  // tools on. Escape closes it again, so the rest of the run starts from rest.
  await page.waitForSelector("#addToss:not([hidden])");
  await page.click("#addToss");
  await page.waitForSelector('#addSheet[data-open="true"]');
  await wait(400);
  await shot(page, "11-add-toss");
  await page.keyboard.press("Escape");
  await page.waitForSelector('#addSheet[data-open="false"]');
  await wait(400);

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

  // 4c. a result that lands while the question is open is not drawn at all. The
  // question keeps the screen, and nothing waits in a queue behind it.
  await post("/api/dev/send", {
    type: "result",
    event_id: 19,
    title: "Bagel",
    big: "-$0.48",
    line: "Food waste, composted",
    tone: "green",
    mass_g: 95,
  });
  await wait(600);
  const underAsk = await page.getAttribute("#resultSheet", "data-open");
  console.log(`result sheet while the question is open: data-open=${underAsk}`);
  if (underAsk !== "false") throw new Error("a result took the question off the screen");

  await page.click("#askSend");
  await page.waitForSelector('#askSheet[data-open="false"]');
  await wait(300);
  await shot(page, "6-learned");
  await wait(3500);
  const afterAnswer = await page.getAttribute("#resultSheet", "data-open");
  if (afterAnswer !== "false") throw new Error("a ticket rose on its own after the answer");
  console.log("nothing rose after the answer, which is the point of dropping the held queue");

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

  // 6b. the hand added toss all the way through, so the mock logs the body and
  // the ticket comes back over the socket like any other.
  await page.click("#addToss");
  await page.waitForSelector('#addSheet[data-open="true"]');
  await page.fill("#addInput", "212");
  await page.click("#addSend");
  await page.waitForSelector('#addSheet[data-open="false"]');
  await page.waitForSelector('#resultSheet[data-open="true"]', { timeout: 6000 });
  await wait(400);
  await shot(page, "12-add-toss-result");
  const addedMass = await page.textContent("#resultMass");
  if (!addedMass.startsWith("212")) throw new Error(`the added toss came back reading ${addedMass}`);
  console.log(`the added toss came back as a ticket reading ${addedMass}`);

  // 8. the chaos script, one step at a time, with the screen checked after each
  // one. The steps live in the mock, so the hand run on a real phone and this
  // run are the same sequence.
  await page.waitForSelector('#resultSheet[data-open="false"]', { state: "attached", timeout: 8000 });
  const steps = (await get("/api/dev/chaos")).steps;
  console.log(`chaos steps: ${steps.join(", ")}`);

  // 8a. a ticket that lands with no figure on it yet
  await chaos("valuing");
  await page.waitForSelector('#resultSheet[data-open="true"]');
  await wait(300);
  await is(page, "#resultWaiting", "Working out the value");
  await hidden(page, "#resultLine", "the advice line while the value is being worked out");
  await shot(page, "c1-valuing");

  // 8b. the same ticket again with its figure. It fills in where it stands, and
  // the weight from the first pass is still there.
  await chaos("figure");
  await wait(400);
  await open(page, "#resultSheet", true, "the ticket stays on the screen for its figure");
  await is(page, "#resultTitle", "Keyboard");
  await is(page, "#resultFigure", "-$20");
  await is(page, "#resultLine", "Removed from register");
  await is(page, "#resultMass", "212 g");
  await hidden(page, "#resultWaiting", "the waiting line once the figure is in");
  await shot(page, "c2-figure");

  // 8c. a tap beside the ticket puts it away
  await page.click("#backdrop", { position: { x: 195, y: 120 } });
  await page.waitForSelector('#resultSheet[data-open="false"]', { state: "attached", timeout: 2000 });
  console.log("a tap beside the ticket dismissed it");

  // 8d. a question landing on top of a ticket takes the screen at once
  await chaos("ask-during-result");
  await page.waitForSelector('#askSheet[data-open="true"]', { timeout: 4000 });
  await open(page, "#resultSheet", false, "the ticket under the question");
  await wait(400);
  await shot(page, "c3-ask-over-ticket");

  // 8e. a tap beside a question leaves it alone
  await page.click("#backdrop", { position: { x: 195, y: 120 } });
  await wait(300);
  await open(page, "#askSheet", true, "the question after a tap beside it");

  // 8f. a ticket landing under an open question is not drawn
  await chaos("result-during-ask");
  await wait(600);
  await open(page, "#resultSheet", false, "a ticket that landed under the question");
  await open(page, "#askSheet", true, "the question while a ticket landed");
  await shot(page, "c4-ticket-under-question");

  // 8g. the socket dies under the open question and comes back by itself
  await chaos("drop-mid-ask");
  await page.waitForSelector('#status[data-state="reconnecting"]', { timeout: 4000 });
  await wait(400);
  await open(page, "#askSheet", true, "the question while the connection is down");
  await shot(page, "c5-reconnect-mid-question");
  await page.waitForSelector('#status[data-state="live"]', { timeout: 20000 });
  await open(page, "#askSheet", true, "the question after the connection came back");
  console.log("the socket came back on its own and the question was still there");

  // 8h. a question says it is still waiting rather than looking dead
  await wait(20500);
  await is(page, "#askWaiting", "Still waiting on you");
  await shot(page, "c6-still-waiting");

  // 8i. Not now sends nothing and clears the question
  await page.click("#askNotNow");
  await page.waitForSelector('#askSheet[data-open="false"]', { state: "attached", timeout: 2000 });
  console.log("Not now cleared the question without sending anything");

  // 8ia. a question that outlives its connection goes by itself, because the
  // backend it belongs to is not there to hear the answer any more.
  await post("/api/dev/send", {
    type: "ask",
    event_id: 27,
    candidates: [{ label: "wrap", p: 0.41 }],
  });
  await page.waitForSelector('#askSheet[data-open="true"]', { timeout: 4000 });
  await post("/api/dev/drop", { refuse_s: 13 });
  await page.waitForSelector('#askSheet[data-open="false"]', { state: "attached", timeout: 13000 });
  console.log("a question left on its own after the connection stayed down");
  await page.waitForSelector('#status[data-state="live"]', { timeout: 30000 });

  // 8j. a ticket whose figure never comes says so and still leaves on its timer
  await chaos("no-figure");
  await page.waitForSelector('#resultSheet[data-open="true"]', { timeout: 4000 });
  await is(page, "#resultWaiting", "Working out the value");
  await wait(8600);
  await is(page, "#resultWaiting", "Value not available");
  await shot(page, "c7-no-value");
  await page.waitForSelector('#resultSheet[data-open="false"]', { state: "attached", timeout: 8000 });
  console.log("the ticket with no figure left on its own");

  // 8ja. a question with no candidates: no buttons, the model's own words above
  // the two ways out of it.
  await chaos("ask-no-candidates");
  await page.waitForSelector('#askSheet[data-open="true"]', { timeout: 4000 });
  const buttons = await page.locator("#askOptions button").count();
  if (buttons !== 0) throw new Error(`a question with no candidates drew ${buttons} buttons`);
  console.log("a question with no candidates drew no buttons");
  await is(page, "#askHeading", "Which is it?");
  await is(
    page,
    "#askLooks",
    "Looks like: a black plastic handle with a frayed cable coming out of it"
  );
  await wait(400);
  await shot(page, "c9-ask-no-candidates");
  await page.click("#askNotNow");
  await page.waitForSelector('#askSheet[data-open="false"]', { state: "attached", timeout: 2000 });

  // 8jb. a question the backend wrote itself takes the place of the heading
  await chaos("ask-question");
  await page.waitForSelector('#askSheet[data-open="true"]', { timeout: 4000 });
  await is(page, "#askHeading", "Is this the broken monitor from the meeting room?");
  await hidden(page, "#askLooks", "the looks line beside a candidate button");
  await wait(400);
  await shot(page, "c10-ask-question");
  await page.click("#askNotNow");
  await page.waitForSelector('#askSheet[data-open="false"]', { state: "attached", timeout: 2000 });

  // 8k. an idle from the backend clears whatever is on the screen
  await post("/api/dev/send", {
    type: "result",
    event_id: 26,
    title: "Mug",
    big: "-$3",
    line: "Broken, landfill",
    tone: "red",
    best_option: "trash",
    mass_g: 320,
  });
  await page.waitForSelector('#resultSheet[data-open="true"]', { timeout: 4000 });
  await chaos("idle");
  await page.waitForSelector('#resultSheet[data-open="false"]', { state: "attached", timeout: 3000 });
  await wait(300);
  await shot(page, "c8-idle");
  console.log("an idle cleared the screen");

  console.log("--- the state machine log for the chaos run ---");
  transitions.forEach((line) => console.log(line));

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

  // 7. the page opened over plain HTTP, when an insecure address is given.
  // Serve the folder with  python -m http.server 8080 --bind 0.0.0.0 --directory phone
  // and pass --http=http://<lan address>:8080/ . It has to be a LAN address, because
  // a browser treats localhost as secure whatever the scheme.
  const insecure = option("http", "");
  if (insecure) {
    const plain = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });
    const plainPage = await plain.newPage();
    watch(plainPage, "http");
    await plainPage.goto(insecure, { waitUntil: "load" });
    await plainPage.waitForSelector("#startError:not([hidden])");
    await wait(300);
    await shot(plainPage, "9-over-http");
    await plain.close();
  }

  await browser.close();
  console.log(`screenshots are in ${OUT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
