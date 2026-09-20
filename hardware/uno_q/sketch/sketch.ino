// The bin's microcontroller side: one load cell, one 240x320 display.
//
// It does two things and nothing else. It reports grams, and it draws whatever screen
// it is told to draw. No thresholds, no filtering, no decisions. All of that is on the
// laptop, which is what makes the bin replaceable and the demo debuggable.
//
// Two ways to reach it, chosen in bin_config.h:
//
//   USE_APP_LAB_RPC 1   the UNO Q's Linux side calls read_grams, tare and show_screen
//                       over Arduino's router bridge
//   USE_APP_LAB_RPC 0   one JSON object per line over a serial port, the same shapes
//                       the firmware contract uses on the socket
//
// The serial form, so it can be read without running anything:
//
//   out: {"t":123456,"g":412.3}
//   in:  {"type":"screen","s":"result","l1":"Keyboard","big":"-$20","l2":"Off books","c":"amber"}
//   in:  {"type":"tare"}
//
// One more line in, which is not part of the firmware contract and which the backend
// never sends. It exists so the two calibration points can be taken with a serial
// monitor and nothing else, and it answers with the raw counts to write down:
//
//   in:  {"type":"calibrate"}
//   out: {"type":"calibration","source":"analog","counts":2048.50,"zero":2040.00,"per_gram":1.0000,"g":8.50}
//
// The weight comes from one of two things, chosen by WEIGHT_SOURCE in bin_config.h: a
// load cell behind an HX711, or a load gauge putting out an analog voltage straight into
// the board's own converter. Nothing above this line changes either way.
//
// Libraries: Adafruit GFX plus one panel driver (see bin_display.h). With the HX711
// source, also HX711 by Bogdan Necula, listed in the Library Manager as "HX711 Arduino
// Library", version 0.7.5; the analog source needs no library at all. On the UNO Q also
// Arduino_RouterBridge, which ships with the UNO Q core.

#include <string.h>

#include "bin_config.h"
#include "bin_display.h"

#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
#include <HX711.h>
#endif

#if USE_APP_LAB_RPC
#include <Arduino_RouterBridge.h>
#endif

// State --------------------------------------------------------------------

#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
HX711 scale;
#endif

static float lastGrams = 0.0f;
// The raw reading behind lastGrams, kept so `calibrate` can report it. On the HX711 it is
// the amplifier's count, on the analog gauge it is the averaged ADC count.
static float lastCounts = 0.0f;
// What the analog gauge read with an empty bin. It starts at the calibrated number and
// tare moves it, which is the same job HX711::tare does on the other path.
static float analogZero = ANALOG_ZERO_COUNTS;
static unsigned long lastWeightAt = 0;
static unsigned long lastHostAt = 0;
static bool offlineDrawn = false;

// What is on the screen now, and what should be. The screen is only redrawn when one
// of these changes, because redrawing a 240x320 panel at 20 Hz is both pointless and
// visibly flickery.
static char curState[12] = "offline";
static char curLine1[LINE_MAX + 1] = "";
static char curBig[BIG_MAX + 1] = "";
static char curLine2[LINE_MAX + 1] = "";
static char curTone[8] = "neutral";

// A screen that arrived from the host and has not been drawn yet. Commands are copied
// here rather than drawn where they arrive, so drawing always happens in loop() and an
// RPC callback can never be painting at the same time as the weight refresh.
static volatile bool pendingScreen = false;
static char newState[12] = "offline";
static char newLine1[LINE_MAX + 1] = "";
static char newBig[BIG_MAX + 1] = "";
static char newLine2[LINE_MAX + 1] = "";
static char newTone[8] = "neutral";

static char serialLine[160];
static size_t serialLen = 0;

// Helpers ------------------------------------------------------------------

static void copyField(char* dest, size_t cap, const char* src) {
  if (src == NULL) {
    dest[0] = '\0';
    return;
  }
  strncpy(dest, src, cap - 1);
  dest[cap - 1] = '\0';
}

// The big figure for the idle and thinking screens. Grams as a whole number and a unit.
// Seven characters hold up to 12345 g, which is far past anything a desk bin will see,
// so there is no case where this needs to shorten itself.
static void formatGrams(float grams, char* dest, size_t cap) {
  long whole = (long)(grams >= 0.0f ? grams + 0.5f : grams - 0.5f);
  snprintf(dest, cap, "%ld g", whole);
  dest[cap - 1] = '\0';
}

static uint16_t toneBackground(const char* tone) {
  if (strcmp(tone, "green") == 0) return TONE_GREEN;
  if (strcmp(tone, "amber") == 0) return TONE_AMBER;
  if (strcmp(tone, "red") == 0) return TONE_RED;
  return TONE_PAPER;
}

static uint16_t toneText(const char* tone) {
  // White on a filled tone, ink on paper. DESIGN.md section 7.
  if (strcmp(tone, "neutral") == 0) return COLOUR_INK;
  return COLOUR_WHITE;
}

// The largest whole text size at which the string still fits the panel width. The
// built-in font is 6 pixels wide per character at size 1.
static uint8_t fitTextSize(const char* text, uint8_t maxSize) {
  size_t len = strlen(text);
  if (len == 0) return maxSize;
  int16_t room = TFT_WIDTH - 2 * SIDE_PADDING;
  for (uint8_t size = maxSize; size > BIG_MIN_SIZE; size--) {
    if ((int16_t)(6 * size * len) <= room) return size;
  }
  return BIG_MIN_SIZE;
}

static int16_t leftX(const char* text) {
  // Left aligned with a margin, or hard against the edge when all 20 characters are
  // used, because 20 characters at size 2 is exactly the width of the panel.
  int16_t width = (int16_t)(strlen(text) * LINE_CHAR_W);
  return (width + 2 * SIDE_PADDING <= TFT_WIDTH) ? SIDE_PADDING : 0;
}

// Drawing ------------------------------------------------------------------

static void drawCurrent() {
  uint16_t background = toneBackground(curTone);
  uint16_t ink = toneText(curTone);

  tft.fillScreen(background);
  tft.setTextWrap(false);
  tft.setTextColor(ink);

  if (curLine1[0] != '\0') {
    tft.setTextSize(LINE_TEXT_SIZE);
    tft.setCursor(leftX(curLine1), LINE1_TOP);
    tft.print(curLine1);
  }

  if (curBig[0] != '\0') {
    uint8_t size = fitTextSize(curBig, BIG_MAX_SIZE);
    int16_t bigW = (int16_t)(6 * size * strlen(curBig));
    int16_t bigH = (int16_t)(8 * size);
    tft.setTextSize(size);
    tft.setCursor((TFT_WIDTH - bigW) / 2, (TFT_HEIGHT - bigH) / 2);
    tft.print(curBig);
  }

  if (curLine2[0] != '\0') {
    tft.setTextSize(LINE_TEXT_SIZE);
    tft.setCursor(leftX(curLine2), TFT_HEIGHT - LINE2_BOTTOM - LINE_CHAR_H);
    tft.print(curLine2);
  }
}

// Redraw only the band the big figure sits in. This is what the idle screen uses as the
// grams tick, so the two text lines are not repainted twenty times a second.
static void drawBigOnly(const char* text) {
  uint16_t background = toneBackground(curTone);
  uint16_t ink = toneText(curTone);
  int16_t band = 8 * BIG_MAX_SIZE;
  int16_t top = (TFT_HEIGHT - band) / 2;

  tft.fillRect(0, top, TFT_WIDTH, band, background);
  if (text[0] == '\0') return;

  uint8_t size = fitTextSize(text, BIG_MAX_SIZE);
  int16_t bigW = (int16_t)(6 * size * strlen(text));
  int16_t bigH = (int16_t)(8 * size);
  tft.setTextWrap(false);
  tft.setTextColor(ink);
  tft.setTextSize(size);
  tft.setCursor((TFT_WIDTH - bigW) / 2, (TFT_HEIGHT - bigH) / 2);
  tft.print(text);
}

// Take a screen command and put it on the panel. The five screens of DESIGN.md
// section 7 are all this one function with different text.
static void applyScreen(const char* state, const char* l1, const char* big, const char* l2,
                        const char* tone) {
  char wantState[12];
  char wantLine1[LINE_MAX + 1];
  char wantBig[BIG_MAX + 1];
  char wantLine2[LINE_MAX + 1];
  char wantTone[8];

  copyField(wantState, sizeof(wantState), state);
  copyField(wantLine1, sizeof(wantLine1), l1);
  copyField(wantBig, sizeof(wantBig), big);
  copyField(wantLine2, sizeof(wantLine2), l2);
  copyField(wantTone, sizeof(wantTone), tone);

  if (strcmp(wantTone, "green") != 0 && strcmp(wantTone, "amber") != 0 &&
      strcmp(wantTone, "red") != 0) {
    copyField(wantTone, sizeof(wantTone), "neutral");
  }

  // The screens that draw the live mass fill in their own text, so the host does not
  // have to send the weight back to the bin that measured it.
  if (strcmp(wantState, "idle") == 0) {
    copyField(wantTone, sizeof(wantTone), "neutral");
    formatGrams(lastGrams, wantBig, sizeof(wantBig));
  } else if (strcmp(wantState, "thinking") == 0) {
    copyField(wantTone, sizeof(wantTone), "neutral");
    if (wantLine1[0] == '\0') copyField(wantLine1, sizeof(wantLine1), "Weighing");
    formatGrams(lastGrams, wantBig, sizeof(wantBig));
  } else if (strcmp(wantState, "ask") == 0) {
    copyField(wantTone, sizeof(wantTone), "neutral");
  } else if (strcmp(wantState, "offline") == 0) {
    copyField(wantTone, sizeof(wantTone), "neutral");
    if (wantLine1[0] == '\0') copyField(wantLine1, sizeof(wantLine1), "Offline");
    if (wantLine2[0] == '\0') copyField(wantLine2, sizeof(wantLine2), "No connection");
  }

  bool same = strcmp(curState, wantState) == 0 && strcmp(curLine1, wantLine1) == 0 &&
              strcmp(curBig, wantBig) == 0 && strcmp(curLine2, wantLine2) == 0 &&
              strcmp(curTone, wantTone) == 0;
  if (same) return;

  bool onlyBig = strcmp(curState, wantState) == 0 && strcmp(curLine1, wantLine1) == 0 &&
                 strcmp(curLine2, wantLine2) == 0 && strcmp(curTone, wantTone) == 0;

  copyField(curState, sizeof(curState), wantState);
  copyField(curLine1, sizeof(curLine1), wantLine1);
  copyField(curBig, sizeof(curBig), wantBig);
  copyField(curLine2, sizeof(curLine2), wantLine2);
  copyField(curTone, sizeof(curTone), wantTone);

  if (onlyBig) {
    drawBigOnly(curBig);
  } else {
    drawCurrent();
  }
}

static void queueScreen(const char* state, const char* l1, const char* big, const char* l2,
                        const char* tone) {
  copyField(newState, sizeof(newState), state);
  copyField(newLine1, sizeof(newLine1), l1);
  copyField(newBig, sizeof(newBig), big);
  copyField(newLine2, sizeof(newLine2), l2);
  copyField(newTone, sizeof(newTone), tone);
  pendingScreen = true;
}

// The scale ----------------------------------------------------------------

#if WEIGHT_SOURCE == WEIGHT_SOURCE_ANALOG

// Average a handful of conversions. The gauge has no instrumentation amplifier in front
// of it, so a single reading jitters by more than a gram and averaging is what makes the
// number usable. Returned as a float because the average of eight integers is not one.
static float readAnalogCounts() {
  uint32_t total = 0;
  for (uint8_t i = 0; i < ANALOG_AVERAGE_OF; i++) {
    total += (uint32_t)analogRead(ANALOG_WEIGHT_PIN);
  }
  return (float)total / (float)ANALOG_AVERAGE_OF;
}

#endif

void tareScale() {
#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
  // HX711::tare(byte times = 10) averages that many readings and stores the offset.
  scale.tare(10);
#else
  // The same idea without a library: whatever the gauge reads now becomes the new zero.
  analogZero = readAnalogCounts();
  lastCounts = analogZero;
#endif
  lastGrams = 0.0f;
}

static void readScale() {
#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
  // is_ready() is false while the amplifier is still converting. Asking anyway would
  // block the loop for up to a tenth of a second at 10 samples per second.
  if (!scale.is_ready()) return;
  lastCounts = scale.get_value(HX711_AVERAGE_OF);
  lastGrams = scale.get_units(HX711_AVERAGE_OF);
#else
  // Two points make a line: the counts at zero, and how far the counts move per gram.
  lastCounts = readAnalogCounts();
  lastGrams = (lastCounts - analogZero) / ANALOG_COUNTS_PER_GRAM;
#endif
}

// What `calibrate` prints. Both numbers the two-point procedure needs are here, so the
// person doing it never has to work anything out on paper: the raw counts to write down,
// and what the sketch currently believes that means in grams.
static void reportCalibration() {
#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
  const char* source = "hx711";
  float zero = 0.0f;
  float perGram = HX711_CALIBRATION;
#else
  const char* source = "analog";
  float zero = analogZero;
  float perGram = ANALOG_COUNTS_PER_GRAM;
#endif
  BIN_SERIAL.print("{\"type\":\"calibration\",\"source\":\"");
  BIN_SERIAL.print(source);
  BIN_SERIAL.print("\",\"counts\":");
  BIN_SERIAL.print(lastCounts, 2);
  BIN_SERIAL.print(",\"zero\":");
  BIN_SERIAL.print(zero, 2);
  BIN_SERIAL.print(",\"per_gram\":");
  BIN_SERIAL.print(perGram, 4);
  BIN_SERIAL.print(",\"g\":");
  BIN_SERIAL.print(lastGrams, 2);
  BIN_SERIAL.println("}");
}

// The serial link ----------------------------------------------------------

// A string field out of one JSON line, without pulling in a JSON library for five
// keys. It finds "key":"value" and copies the value. Escapes are not handled, and the
// backend never sends any: every field it sends has already been cut to plain text.
static bool jsonString(const char* line, const char* key, char* dest, size_t cap) {
  char needle[16];
  snprintf(needle, sizeof(needle), "\"%s\"", key);
  const char* at = strstr(line, needle);
  dest[0] = '\0';
  if (at == NULL) return false;
  at = strchr(at + strlen(needle), ':');
  if (at == NULL) return false;
  at++;
  while (*at == ' ') at++;
  if (*at != '"') return false;
  at++;
  size_t n = 0;
  while (*at != '"' && *at != '\0' && n + 1 < cap) {
    dest[n++] = *at++;
  }
  dest[n] = '\0';
  return true;
}

static void handleLine(const char* line) {
  lastHostAt = millis();
  char type[16];
  if (!jsonString(line, "type", type, sizeof(type))) return;

  if (strcmp(type, "tare") == 0) {
    tareScale();
    return;
  }
  // Not part of the firmware contract and never sent by the backend. It exists so the
  // two calibration points can be taken with nothing but a serial monitor.
  if (strcmp(type, "calibrate") == 0) {
    readScale();
    reportCalibration();
    return;
  }
  if (strcmp(type, "screen") != 0) return;

  char state[12];
  char l1[LINE_MAX + 1];
  char big[BIG_MAX + 1];
  char l2[LINE_MAX + 1];
  char tone[8];
  jsonString(line, "s", state, sizeof(state));
  jsonString(line, "l1", l1, sizeof(l1));
  jsonString(line, "big", big, sizeof(big));
  jsonString(line, "l2", l2, sizeof(l2));
  jsonString(line, "c", tone, sizeof(tone));
  queueScreen(state, l1, big, l2, tone);
}

static void pumpSerial() {
  while (BIN_SERIAL.available() > 0) {
    char c = (char)BIN_SERIAL.read();
    if (c == '\n' || c == '\r') {
      if (serialLen > 0) {
        serialLine[serialLen] = '\0';
        handleLine(serialLine);
        serialLen = 0;
      }
      continue;
    }
    if (serialLen + 1 < sizeof(serialLine)) {
      serialLine[serialLen++] = c;
    }
  }
}

static void reportWeight() {
  BIN_SERIAL.print("{\"t\":");
  BIN_SERIAL.print(millis());
  BIN_SERIAL.print(",\"g\":");
  BIN_SERIAL.print(lastGrams, 2);
  BIN_SERIAL.println("}");
}

// The App Lab router bridge ------------------------------------------------

#if USE_APP_LAB_RPC

// The Linux side calls these three by name. Arduino_RouterBridge registers them with
// Bridge.provide, and the Python side reaches them with Bridge.call and Bridge.notify.
//
// Answered: provide_safe does accept a handler of five String arguments. Built clean
// against Arduino_RouterBridge 0.4.3 on arduino:zephyr 1.0.0, with both panel drivers.
// The fallback below is therefore not needed and is kept only as a note.
//
// NEEDS_HARDWARE_CHECK: the five argument form compiles, but nothing has called it yet.
// If a call from the Linux side misbehaves on the real board, send the screen as one
// JSON string instead: change show_screen to take a single String, and call handleLine
// on it, which is the same parser the serial path uses.

float rpcReadGrams() {
  lastHostAt = millis();
  return lastGrams;
}

bool rpcTare() {
  lastHostAt = millis();
  tareScale();
  return true;
}

// The two calibration points over the bridge, for when there is no serial adapter to
// hand. Returns the raw counts, which is the number the procedure asks you to write down.
float rpcCalibrate() {
  lastHostAt = millis();
  readScale();
  reportCalibration();
  return lastCounts;
}

bool rpcShowScreen(String state, String l1, String big, String l2, String tone) {
  lastHostAt = millis();
  queueScreen(state.c_str(), l1.c_str(), big.c_str(), l2.c_str(), tone.c_str());
  return true;
}

#endif  // USE_APP_LAB_RPC

// Setup and loop -----------------------------------------------------------

void setup() {
  BIN_SERIAL.begin(SERIAL_BAUD);

#if TFT_BACKLIGHT_PIN >= 0
  pinMode(TFT_BACKLIGHT_PIN, OUTPUT);
  digitalWrite(TFT_BACKLIGHT_PIN, HIGH);
#endif

  panelBegin();
  copyField(curState, sizeof(curState), "boot");
  applyScreen("offline", "Starting", "", "Zeroing the scale", "neutral");

#if WEIGHT_SOURCE == WEIGHT_SOURCE_HX711
  // HX711::begin(byte dout, byte pd_sck, byte gain = 128). Gain 128 is channel A, the
  // one a load cell bridge is wired to.
  scale.begin(HX711_DT_PIN, HX711_SCK_PIN);
  scale.set_scale(HX711_CALIBRATION);
  scale.tare(10);
#else
  // Ask the converter for its full width before the first reading, so the calibration
  // numbers and the live readings are on the same scale.
  analogReadResolution(ANALOG_READ_BITS);
  pinMode(ANALOG_WEIGHT_PIN, INPUT);
  tareScale();
#endif

#if USE_APP_LAB_RPC
  Bridge.begin();
  Bridge.provide_safe("read_grams", rpcReadGrams);
  Bridge.provide_safe("tare", rpcTare);
  Bridge.provide_safe("calibrate", rpcCalibrate);
  Bridge.provide_safe("show_screen", rpcShowScreen);
#endif

  lastHostAt = millis();
  lastWeightAt = millis();
  applyScreen("offline", "", "", "", "neutral");
}

void loop() {
#if !USE_APP_LAB_RPC
  pumpSerial();
#endif

  unsigned long now = millis();

  if (now - lastWeightAt >= WEIGHT_PERIOD_MS) {
    lastWeightAt = now;
    readScale();
#if !USE_APP_LAB_RPC
    reportWeight();
#endif
    // The idle and thinking screens show the live mass, so they are refreshed in place
    // whenever the reading moves. applyScreen does nothing when the text is unchanged.
    if (strcmp(curState, "idle") == 0 || strcmp(curState, "thinking") == 0) {
      applyScreen(curState, curLine1, curBig, curLine2, curTone);
    }
  }

  if (pendingScreen) {
    pendingScreen = false;
    applyScreen(newState, newLine1, newBig, newLine2, newTone);
    offlineDrawn = false;
  }

  // firmware_contract.md: nothing from the host for 5 s and the bin says so itself,
  // without being told. This is the one decision the firmware makes on its own.
  if (now - lastHostAt >= OFFLINE_AFTER_MS && !offlineDrawn) {
    offlineDrawn = true;
    applyScreen("offline", "", "", "", "neutral");
  }
}
