// The 240x320 panel, behind one name.
//
// Both drivers are Adafruit GFX underneath, so every drawing call in the sketch is the
// same either way. Only the constructor and the start-up call differ, and that
// difference lives here. Pick the driver in bin_config.h.
//
// Libraries to install, by the names the Arduino Library Manager lists:
//   Adafruit GFX Library
//   Adafruit ILI9341        (when USE_ILI9341 is 1)
//   Adafruit ST7735 and ST7789 Library  (when USE_ST7789 is 1)
//   Adafruit BusIO          (a dependency of the two drivers, installed with them)

#ifndef BIN_DISPLAY_H
#define BIN_DISPLAY_H

#include <Adafruit_GFX.h>

#include "bin_config.h"

#if USE_ILI9341

#include <Adafruit_ILI9341.h>

static Adafruit_ILI9341 tft(TFT_CS_PIN, TFT_DC_PIN, TFT_RST_PIN);

inline void panelBegin() {
  // Adafruit_ILI9341::begin(uint32_t freq = 0), 0 meaning the library's default speed.
  tft.begin();
  tft.setRotation(TFT_ROTATION);
}

#elif USE_ST7789

#include <Adafruit_ST7789.h>

static Adafruit_ST7789 tft(TFT_CS_PIN, TFT_DC_PIN, TFT_RST_PIN);

inline void panelBegin() {
  // This driver has no begin(). It takes the panel size:
  // init(uint16_t width, uint16_t height, uint8_t spiMode = SPI_MODE0).
  tft.init(TFT_WIDTH, TFT_HEIGHT);
  tft.setRotation(TFT_ROTATION);
}

#else
#error "Set USE_ILI9341 or USE_ST7789 to 1 in bin_config.h"
#endif

#endif  // BIN_DISPLAY_H
