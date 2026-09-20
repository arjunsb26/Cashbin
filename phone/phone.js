"use strict";

/* The phone camera page. Plain ES2020, no build step, no dependencies.
   It streams JPEG frames to the backend over a secure WebSocket and draws
   the tickets and questions the backend sends back. */

/* ---- settings ---- */

const FRAME_WIDTH = 640;
const FRAME_INTERVAL_MS = 125; // about 8 frames a second
const FRAME_QUALITY = 0.7;
const FRAME_BYTES_GUESS = 24000; // used before the first frame is measured
const RESULT_MS = 6000; // a ticket leaves after this long with no update
const VALUING_MS = 8000; // how long a ticket waits for its figure before it gives up
const ASK_WAIT_MS = 20000; // when a question starts saying it is still waiting
const ASK_DROP_MS = 10000; // how long a question survives a dropped connection
const LEARNED_MS = 2500;
const TOOLTIP_MS = 4000;
const BACKOFF_MIN_MS = 500;
const BACKOFF_MAX_MS = 8000;
const LABEL_MAX = 40;
const MASS_DEFAULT = "150";
const MASS_MAX_G = 100000;

const TONES = ["green", "amber", "red", "neutral"];

/* ---- elements ---- */

const el = (id) => document.getElementById(id);

const startScreen = el("startScreen");
const cameraScreen = el("cameraScreen");
const brandName = el("brandName");
const startButton = el("startButton");
const startError = el("startError");
const video = el("video");
const status = el("status");
const statusPill = el("statusPill");
const statusText = el("statusText");
const statusTooltip = el("statusTooltip");
const statusMessage = el("statusMessage");
const cameraError = el("cameraError");
const learnedLine = el("learnedLine");
const backdrop = el("backdrop");
const resultSheet = el("resultSheet");
const resultTitle = el("resultTitle");
const resultMass = el("resultMass");
const resultFigure = el("resultFigure");
const resultLine = el("resultLine");
const resultWaiting = el("resultWaiting");
const askSheet = el("askSheet");
const askCrop = el("askCrop");
const askOptions = el("askOptions");
const askOther = el("askOther");
const askField = el("askField");
const askInput = el("askInput");
const askReadBack = el("askReadBack");
const askSend = el("askSend");
const askNotNow = el("askNotNow");
const askNote = el("askNote");
const askWaiting = el("askWaiting");
const addToss = el("addToss");
const addSheet = el("addSheet");
const addInput = el("addInput");
const addNote = el("addNote");
const addSend = el("addSend");
const addCancel = el("addCancel");

/* ---- state ---- */

let stream = null;
let cameraRunning = false;
let socket = null;
let reconnectAttempts = 0;
let reconnectTimer = 0;
let frameTimer = 0;
let rateTimer = 0;
let encoding = false;
let framesThisSecond = 0;
let framesPerSecond = 0;
let droppedThisSecond = 0;
let droppedPerSecond = 0;
let lastFrameBytes = FRAME_BYTES_GUESS;
let learnedTimer = 0;
let tooltipTimer = 0;
let answering = false;
let wakeLock = null;
let adding = false;
let restartingCamera = false;

/* The sheet state machine. One of "idle", "result", "ask", "adding" is on the
   screen at any moment, never two. Every move through it is logged with the
   event it belongs to, so a phone that looks stuck can be read back. */
let sheetState = "idle";
let resultEventId = null;
let resultShown = null; // the message on the screen, so a second pass can fill it in
let askEventId = null;
let resultTimer = 0;
let valuingTimer = 0;
let askWaitTimer = 0;
let askDropTimer = 0;

const canvas = document.createElement("canvas");
const context = canvas.getContext("2d", { alpha: false });

/* ---- small helpers ---- */

function text(value, max) {
  if (typeof value !== "string") return "";
  return value.replace(/\s+/g, " ").trim().slice(0, max);
}

function wholeNumber(value) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function percent(value) {
  if (typeof value !== "number" || !isFinite(value)) return "";
  const clamped = Math.min(1, Math.max(0, value));
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 0 }).format(clamped);
}

function show(node, message) {
  node.textContent = message;
  node.hidden = false;
}

function hide(node) {
  node.hidden = true;
  node.textContent = "";
}

function setThemeColour() {
  const paper = getComputedStyle(document.documentElement).getPropertyValue("--paper").trim();
  const meta = el("themeColor");
  if (paper && meta) meta.setAttribute("content", paper);
}

/* ---- the product name ---- */

async function loadBrand() {
  brandName.textContent = document.title;
  try {
    const res = await fetch("/brand.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    const name = text(data && data.name, 40);
    if (!name) return;
    document.title = name;
    brandName.textContent = name;
  } catch (err) {
    // The page keeps its own title when the brand file cannot be read.
  }
}

/* ---- the camera ---- */

function cameraSentence(err) {
  const name = err && err.name ? err.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Camera access was refused. Allow the camera for this page in your browser settings, then tap Start camera again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError" || name === "DevicesNotFoundError") {
    return "No camera was found on this device.";
  }
  if (name === "NotReadableError" || name === "TrackStartError" || name === "AbortError") {
    return "The camera is busy in another app. Close that app, then tap Start camera again.";
  }
  return "The camera did not start. Tap Start camera again.";
}

async function startCamera() {
  hide(startError);
  if (!window.isSecureContext) {
    show(startError, "This page must be opened over HTTPS. Browsers keep the camera off on an insecure connection.");
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    show(startError, "This browser does not let a web page use the camera.");
    return;
  }

  startButton.disabled = true;
  let next;
  try {
    next = await openStream();
  } catch (err) {
    startButton.disabled = false;
    show(startError, cameraSentence(err));
    return;
  }

  await attachStream(next);

  cameraRunning = true;
  startScreen.hidden = true;
  cameraScreen.hidden = false;
  startButton.disabled = false;

  requestWakeLock();
  connect();
  startFrameTimer();
}

function openStream() {
  return navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
  });
}

async function attachStream(next) {
  stream = next;
  video.srcObject = next;
  next.getVideoTracks().forEach((track) => {
    track.addEventListener("ended", onTrackEnded);
  });
  try {
    await video.play();
  } catch (err) {
    // Some browsers resolve the stream but defer play. The frame timer waits
    // for readyState, so a deferred play costs nothing.
  }
  hide(cameraError);
}

function stopStream() {
  if (!stream) return;
  stream.getTracks().forEach((track) => {
    track.removeEventListener("ended", onTrackEnded);
    try {
      track.stop();
    } catch (err) {
      // A track that has already ended throws on some builds of WebKit.
    }
  });
  stream = null;
}

function cameraLive() {
  if (!stream) return false;
  return stream.getVideoTracks().some((track) => track.readyState === "live");
}

/* iOS ends the camera track when the page goes to the background. The page picks
   it up again by itself when the person comes back, with no tap and no reload. */
function onTrackEnded() {
  if (document.visibilityState !== "visible") return;
  restartCamera();
}

async function restartCamera() {
  if (restartingCamera || !cameraRunning || cameraLive()) return;
  restartingCamera = true;
  stopStream();
  let next;
  try {
    next = await openStream();
  } catch (err) {
    restartingCamera = false;
    // The camera is not coming back on its own, so the way back in is a tap.
    cameraRunning = false;
    clearSheets("the camera stopped");
    hide(cameraError);
    cameraScreen.hidden = true;
    startScreen.hidden = false;
    startButton.disabled = false;
    show(startError, cameraSentence(err));
    return;
  }
  await attachStream(next);
  restartingCamera = false;
}

function startFrameTimer() {
  if (frameTimer) return;
  frameTimer = setInterval(sendFrame, FRAME_INTERVAL_MS);
  rateTimer = setInterval(() => {
    framesPerSecond = framesThisSecond;
    droppedPerSecond = droppedThisSecond;
    framesThisSecond = 0;
    droppedThisSecond = 0;
    updateTooltipText();
  }, 1000);
}

function sendFrame() {
  if (!cameraRunning || encoding) return;
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  if (video.readyState < 2 || !video.videoWidth) return;

  const scale = FRAME_WIDTH / video.videoWidth;
  const width = FRAME_WIDTH;
  const height = Math.max(1, Math.round(video.videoHeight * scale));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  context.drawImage(video, 0, 0, width, height);

  encoding = true;
  canvas.toBlob(
    (blob) => {
      encoding = false;
      if (!blob || !socket || socket.readyState !== WebSocket.OPEN) return;
      // Drop a frame rather than queue it. A slow link must not build latency.
      if (socket.bufferedAmount > lastFrameBytes * 2) {
        droppedThisSecond += 1;
        return;
      }
      socket.send(blob);
      lastFrameBytes = blob.size;
      framesThisSecond += 1;
    },
    "image/jpeg",
    FRAME_QUALITY
  );
}

/* ---- the socket ---- */

function socketUrl() {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  return scheme + "//" + location.host + "/ws/phone";
}

function connect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = 0;
  }
  let ws;
  try {
    ws = new WebSocket(socketUrl());
  } catch (err) {
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.addEventListener("open", () => {
    if (socket !== ws) return;
    reconnectAttempts = 0;
    setStatus("live");
    hide(statusMessage);
    if (askDropTimer) {
      clearTimeout(askDropTimer);
      askDropTimer = 0;
    }
    // The hello goes first and the frames follow on the timer that never stopped,
    // so coming back costs no tap and no reload.
    send({ type: "hello", ua: navigator.userAgent });
    console.info("socket: open, hello sent, frames resume");
  });

  ws.addEventListener("message", (event) => {
    if (socket !== ws) return;
    if (typeof event.data !== "string") return;
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    if (!message || typeof message.type !== "string") return;
    handle(message);
  });

  ws.addEventListener("close", () => {
    if (socket !== ws) return;
    socket = null;
    onDisconnected();
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    if (socket !== ws) return;
    try {
      ws.close();
    } catch (err) {
      // close on a socket that never opened throws in some browsers
    }
  });
}

function scheduleReconnect() {
  setStatus("reconnecting");
  if (reconnectAttempts >= 2) {
    show(statusMessage, "The connection dropped. Trying again.");
  }
  const delay = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * Math.pow(2, reconnectAttempts));
  reconnectAttempts += 1;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connect, delay);
}

/* What is on the screen when the connection goes belongs to the session that
   went with it. The ticket goes at once, because it is only ever a few seconds
   old. The question is given ten seconds to survive a blip, because the answer
   travels over its own request and still lands, and then it goes too rather
   than sit there unanswerable. */
function onDisconnected() {
  console.info("socket: closed");
  if (sheetState === "result") {
    dismissResult("the connection dropped");
    return;
  }
  if (sheetState === "ask" && !askDropTimer) {
    askDropTimer = setTimeout(() => {
      askDropTimer = 0;
      if (sheetState === "ask") closeAsk("the connection stayed down");
    }, ASK_DROP_MS);
  }
}

function clearSheets(why) {
  if (sheetState === "idle") return;
  if (sheetState === "result") {
    dismissResult(why);
    return;
  }
  if (sheetState === "ask") {
    closeAsk(why);
    return;
  }
  closeAdd();
}

function send(message) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify(message));
}

function handle(message) {
  if (message.type === "ping") {
    send({ type: "pong" });
    return;
  }
  if (message.type === "result") {
    onResult(message);
    return;
  }
  if (message.type === "ask") {
    onAsk(message);
    return;
  }
  if (message.type === "idle") {
    onIdle();
  }
}

/* ---- status pill ---- */

function setStatus(state) {
  status.dataset.state = state;
  statusText.textContent = state === "live" ? "Live" : "Reconnecting";
}

function updateTooltipText() {
  let line = framesPerSecond
    ? wholeNumber(framesPerSecond) + " frames a second"
    : "No frames are going out";
  if (droppedPerSecond) line += ", " + wholeNumber(droppedPerSecond) + " dropped";
  statusTooltip.textContent = line;
  statusPill.title = line;
}

function toggleTooltip() {
  if (!statusTooltip.hidden) {
    statusTooltip.hidden = true;
    return;
  }
  updateTooltipText();
  statusTooltip.hidden = false;
  if (tooltipTimer) clearTimeout(tooltipTimer);
  tooltipTimer = setTimeout(() => {
    statusTooltip.hidden = true;
  }, TOOLTIP_MS);
}

/* ---- the sheet state machine ----
   Four states, one on the screen at a time: idle, result, ask, adding.

   A result for the event already on the screen fills that ticket in where it
   stands. A result for a newer event takes its place. A question wins over any
   ticket and shows the moment it lands. An idle from the backend clears the
   screen. Nothing is queued and nothing waits its turn, so nothing can pile up
   behind a message that never comes. */

function setSheetOpen(sheet, open) {
  sheet.dataset.open = open ? "true" : "false";
  sheet.inert = !open;
}

function named(eventId) {
  return eventId === null || eventId === undefined ? "none" : String(eventId);
}

function setState(next, eventId, why) {
  const from = sheetState;
  sheetState = next;
  console.info("sheet: " + from + " to " + next + ", event " + named(eventId) + ", " + why);
  renderSheets();
}

function stay(eventId, why) {
  console.info("sheet: stays " + sheetState + ", event " + named(eventId) + ", " + why);
}

function renderSheets() {
  setSheetOpen(resultSheet, sheetState === "result");
  setSheetOpen(askSheet, sheetState === "ask");
  setSheetOpen(addSheet, sheetState === "adding");
  const covered = sheetState === "result" || sheetState === "ask";
  backdrop.dataset.open = covered ? "true" : "false";
  backdrop.hidden = !covered;
}

function tone(value) {
  return TONES.indexOf(value) === -1 ? "neutral" : value;
}

function eventOf(message) {
  return Number.isInteger(message.event_id) ? message.event_id : null;
}

/* The backend posts a ticket it cannot price yet twice: once with a placeholder
   where the money goes, then again with the figure. The placeholder is how the
   page knows a second pass is still coming. */
function isValuing(message) {
  return text(message.big, 16).replace(/[.…·-]/g, "").length === 0;
}

function clearResultTimers() {
  if (resultTimer) {
    clearTimeout(resultTimer);
    resultTimer = 0;
  }
  if (valuingTimer) {
    clearTimeout(valuingTimer);
    valuingTimer = 0;
  }
}

function clearAskTimers() {
  if (askWaitTimer) {
    clearTimeout(askWaitTimer);
    askWaitTimer = 0;
  }
}

function forgetResult() {
  clearResultTimers();
  resultEventId = null;
  resultShown = null;
}

/* ---- tickets ---- */

function onResult(message) {
  const eventId = eventOf(message);
  if (sheetState === "ask") {
    stay(eventId, "a question is open, so this ticket is not drawn");
    return;
  }
  if (sheetState === "adding") {
    stay(eventId, "a weight is being typed, so this ticket is not drawn");
    return;
  }
  if (
    sheetState === "result" &&
    eventId !== null &&
    resultEventId !== null &&
    eventId < resultEventId
  ) {
    stay(eventId, "an older ticket than the one on the screen");
    return;
  }
  const sameEvent = sheetState === "result" && eventId !== null && eventId === resultEventId;
  drawResult(message, sameEvent);
  if (sameEvent) {
    stay(eventId, "the same ticket, filled in where it stands");
  } else {
    setState("result", eventId, "a ticket arrived");
  }
}

function drawResult(message, sameEvent) {
  // A second pass that leaves a field out keeps what the first pass carried, so
  // the weight does not vanish when the figure turns up.
  const base = sameEvent && resultShown ? resultShown : {};
  const shown = Object.assign({}, base, message);
  if (typeof shown.mass_g !== "number" && typeof base.mass_g === "number") {
    shown.mass_g = base.mass_g;
  }
  resultShown = shown;
  resultEventId = eventOf(message);

  const valuing = isValuing(shown);
  resultSheet.dataset.tone = tone(shown.tone);
  resultTitle.textContent = text(shown.title, 60) || "Ticket";
  const big = text(shown.big, 12);
  resultFigure.textContent = big;
  // The backend sends the figure already shaped for the LCD, so the page reads
  // the sign off the front of it rather than formatting the number again.
  resultFigure.dataset.sign = big.startsWith("-") || big.startsWith("(") ? "negative" : "positive";

  if (valuing) {
    // The advice line is the backend's to write, and there is none on this pass,
    // so the sheet says what it is doing in its own words until the figure lands.
    resultLine.hidden = true;
    resultLine.textContent = "";
    show(resultWaiting, "Working out the value");
  } else {
    hide(resultWaiting);
    resultLine.textContent = text(shown.line, 80);
    resultLine.hidden = false;
  }

  const grams = typeof shown.mass_g === "number" && isFinite(shown.mass_g) ? shown.mass_g : null;
  if (grams === null) {
    resultMass.hidden = true;
    resultMass.textContent = "";
  } else {
    // Thin space between the number and its unit, DESIGN.md section 2.
    resultMass.textContent = wholeNumber(grams) + " g";
    resultMass.hidden = false;
  }

  if (!sameEvent && typeof navigator.vibrate === "function") {
    try {
      navigator.vibrate(10);
    } catch (err) {
      // iOS has no vibrate. Nothing to report to the person here.
    }
  }

  clearResultTimers();
  if (valuing) {
    // A ticket waiting on its figure does not start its six seconds yet, or it
    // would leave the screen before the thing it is waiting for arrives.
    valuingTimer = setTimeout(giveUpOnValue, VALUING_MS);
  } else {
    resultTimer = setTimeout(() => dismissResult("six seconds with no update"), RESULT_MS);
  }
}

function giveUpOnValue() {
  valuingTimer = 0;
  if (sheetState !== "result") return;
  show(resultWaiting, "Value not available");
  stay(resultEventId, "no figure arrived, so the ticket leaves on its timer");
  resultTimer = setTimeout(() => dismissResult("six seconds with no update"), RESULT_MS);
}

function dismissResult(why) {
  clearResultTimers();
  if (sheetState !== "result") return;
  const eventId = resultEventId;
  resultEventId = null;
  resultShown = null;
  setState("idle", eventId, why);
}

/* ---- questions ---- */

function onAsk(message) {
  forgetResult();
  clearAskTimers();
  hide(learnedLine);

  const eventId = eventOf(message);
  askEventId = eventId;
  answering = false;

  const candidates = Array.isArray(message.candidates) ? message.candidates.slice(0, 4) : [];
  askOptions.textContent = "";
  candidates.forEach((candidate) => {
    const name = text(candidate && candidate.label, LABEL_MAX);
    if (!name) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button--candidate";
    const word = document.createElement("span");
    word.textContent = name;
    const p = document.createElement("span");
    p.className = "ask__p";
    p.textContent = percent(candidate.p);
    button.append(word, p);
    button.addEventListener("click", () => answer(name));
    askOptions.append(button);
  });

  askCrop.hidden = true;
  if (eventId !== null) {
    askCrop.src = "/media/" + eventId + "/crop.jpg";
  }

  askField.hidden = true;
  askInput.value = "";
  askReadBack.textContent = "";
  askSend.disabled = true;
  askOther.hidden = false;
  askNotNow.disabled = false;
  hide(askNote);
  hide(askWaiting);
  // A question never times out. After a while it says it is still waiting, so a
  // screen that is holding still does not read as a screen that has died.
  askWaitTimer = setTimeout(() => {
    askWaitTimer = 0;
    if (sheetState === "ask") show(askWaiting, "Still waiting on you");
  }, ASK_WAIT_MS);

  setState("ask", eventId, "a question arrived");
}

function closeAsk(why) {
  clearAskTimers();
  askEventId = null;
  hide(askWaiting);
  if (sheetState !== "ask") return;
  setState("idle", null, why);
}

function notNow() {
  if (answering) return;
  // Nothing is sent. The question leaves this screen and the bin keeps it open,
  // which is what the dashboard is there for.
  closeAsk("tapped Not now");
}

/* ---- the backend says nothing is happening ---- */

function onIdle() {
  if (sheetState === "result") {
    dismissResult("the backend went idle");
    return;
  }
  if (sheetState === "ask") {
    closeAsk("the backend went idle");
    return;
  }
  stay(null, "the backend went idle");
}

/* ---- a tap beside a sheet ---- */

function tapOutside() {
  if (sheetState === "result") {
    dismissResult("tapped beside the ticket");
    return;
  }
  stay(null, "tapped beside a question, which stays until it is answered");
}

/* ---- the free text answer ----
   Typed text never travels as an instruction. It is read into one field with a
   fixed shape: trimmed, lowercased, letters, digits, spaces and hyphens only,
   at most 40 characters. The person sees what was understood and what was
   dropped before it is sent. The backend reads it again the same way. */

function readLabel(raw) {
  const notes = [];
  const original = typeof raw === "string" ? raw : "";
  let value = original.trim();
  const whitelisted = value.replace(/[^A-Za-z0-9 -]/g, "");
  if (whitelisted !== value) {
    notes.push("Anything that was not a letter, digit, space or hyphen was left out.");
  }
  value = whitelisted.replace(/ +/g, " ").trim().toLowerCase();
  if (value.length > LABEL_MAX) {
    value = value.slice(0, LABEL_MAX).trim();
    notes.push("Only the first " + LABEL_MAX + " characters were kept.");
  }
  return { value: value, notes: notes };
}

function onLabelInput() {
  const read = readLabel(askInput.value);
  askSend.disabled = read.value.length === 0 || answering;
  if (!askInput.value.trim()) {
    askReadBack.textContent = "";
    return;
  }
  if (!read.value) {
    askReadBack.textContent = "Nothing usable yet. Use letters, digits, spaces or hyphens.";
    return;
  }
  const parts = ["Understood as “" + read.value + "”."];
  askReadBack.textContent = parts.concat(read.notes).join(" ");
}

function revealOther() {
  askOther.hidden = true;
  askField.hidden = false;
  askInput.focus();
}

/* ---- answering ---- */

async function answer(label) {
  if (answering || askEventId === null) return;
  const read = readLabel(label);
  if (!read.value) return;
  answering = true;
  setAskDisabled(true);
  hide(askNote);

  try {
    const res = await fetch("/api/corrections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_id: askEventId, label: read.value }),
    });
    if (!res.ok) throw new Error("rejected");
  } catch (err) {
    answering = false;
    setAskDisabled(false);
    show(askNote, "The answer did not send. Tap it again.");
    return;
  }

  answering = false;
  closeAsk("answered");
  show(learnedLine, "Learned. Next time this is recognised without asking.");
  if (learnedTimer) clearTimeout(learnedTimer);
  learnedTimer = setTimeout(() => hide(learnedLine), LEARNED_MS);
}

function setAskDisabled(disabled) {
  const buttons = askSheet.querySelectorAll("button");
  buttons.forEach((button) => {
    button.disabled = disabled;
  });
  if (!disabled) onLabelInput();
}

/* ---- adding a toss by hand ----
   A way to make a ticket without the scale or a laptop terminal. The control is
   drawn only when the backend still has its simulator routes mounted, so the
   demo build shows nothing at all here, not a disabled button. */

async function checkDevTools() {
  try {
    const res = await fetch("/api/sim/expect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    // The route is gone in the demo build. Any other answer, including a
    // complaint about the empty body, means the route is there.
    if (res.status === 404) return;
  } catch (err) {
    return;
  }
  addToss.hidden = false;
}

/* The weight is read into a number before it goes anywhere: digits and at most
   one point, above zero, at or below the cap. Nothing else leaves this page. */
function readMass(raw) {
  const cleaned = String(raw == null ? "" : raw).replace(/[^0-9.]/g, "");
  const parts = cleaned.split(".");
  const joined = parts.length > 2 ? parts[0] + "." + parts.slice(1).join("") : cleaned;
  const value = Number.parseFloat(joined);
  if (!isFinite(value) || value <= 0 || value > MASS_MAX_G) return null;
  return value;
}

function openAdd() {
  if (addToss.hidden) return;
  // A question stays on the screen until it is answered, so it is not covered.
  if (sheetState === "ask") {
    stay(askEventId, "a question is open, so the weight box does not open over it");
    return;
  }
  forgetResult();
  adding = false;
  addInput.value = MASS_DEFAULT;
  hide(addNote);
  setAddDisabled(false);
  setState("adding", null, "opened the weight box");
  addInput.focus();
  addInput.select();
}

function closeAdd() {
  if (sheetState !== "adding") return;
  setState("idle", null, "closed the weight box");
}

function setAddDisabled(disabled) {
  addSend.disabled = disabled;
  addCancel.disabled = disabled;
  addInput.disabled = disabled;
}

async function sendToss() {
  if (adding) return;
  const mass = readMass(addInput.value);
  if (mass === null) {
    show(addNote, "Type the weight in grams, above zero.");
    addInput.focus();
    return;
  }
  adding = true;
  setAddDisabled(true);
  hide(addNote);

  let res;
  try {
    res = await fetch("/api/sim/toss", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mass_g: mass }),
    });
  } catch (err) {
    adding = false;
    setAddDisabled(false);
    show(addNote, "The toss did not go in. Try again.");
    return;
  }

  if (!res.ok) {
    let sentence = "";
    if (res.status === 409) {
      try {
        const body = await res.json();
        sentence = text(body && body.detail, 160);
      } catch (err) {
        sentence = "";
      }
    }
    adding = false;
    setAddDisabled(false);
    show(addNote, sentence || "The toss did not go in. Try again.");
    return;
  }

  adding = false;
  setAddDisabled(false);
  closeAdd();
  // The ticket comes back over the socket, the same way a real toss does.
}

/* ---- wake lock ---- */

async function requestWakeLock() {
  if (!("wakeLock" in navigator)) return;
  try {
    wakeLock = await navigator.wakeLock.request("screen");
    wakeLock.addEventListener("release", () => {
      wakeLock = null;
    });
  } catch (err) {
    // A browser without screen wake lock just keeps its own screen timeout.
  }
}

/* ---- wiring ---- */

startButton.addEventListener("click", startCamera);
statusPill.addEventListener("click", toggleTooltip);
resultSheet.addEventListener("click", () => dismissResult("tapped the ticket"));
backdrop.addEventListener("click", tapOutside);
askOther.addEventListener("click", revealOther);
askNotNow.addEventListener("click", notNow);
askInput.addEventListener("input", onLabelInput);
askSend.addEventListener("click", () => answer(askInput.value));
askCrop.addEventListener("error", () => {
  askCrop.hidden = true;
});
askCrop.addEventListener("load", () => {
  askCrop.hidden = false;
});
addToss.addEventListener("click", openAdd);
addSend.addEventListener("click", sendToss);
addCancel.addEventListener("click", closeAdd);
addInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendToss();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || addSheet.dataset.open !== "true" || adding) return;
  event.preventDefault();
  closeAdd();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || !cameraRunning) return;
  requestWakeLock();
  restartCamera();
});

renderSheets();
setThemeColour();
loadBrand();
checkDevTools();

if (!window.isSecureContext) {
  show(startError, "This page must be opened over HTTPS. Browsers keep the camera off on an insecure connection.");
}
