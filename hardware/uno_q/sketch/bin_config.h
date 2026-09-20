// Every number the bin's firmware depends on, in one place.
//
// The pins are the part nobody can decide from a laptop. Each one is marked
// NEEDS_HARDWARE_CHECK with the question to answer once the board and the display are
// in hand. Nothing else in the sketch hardcodes a pin.

#ifndef BIN_CONFIG_H
#define BIN_CONFIG_H

#include <Arduino.h>

// Display driver. Set exactly one to 1. A 240x320 SPI panel is almost always one of
// these two, and they share the Adafruit GFX drawing calls, so only the constructor
// and the init call differ.
#define USE_ILI9341 0
#define USE_ST7789 1

// Set to 1 once Arduino App Lab's RPC names are confirmed on the board. See the
// NEEDS_HARDWARE_CHECK block at the bottom of binbooks_bin.ino. With this at 0 the
// sketch talks over the serial link instead, which needs no board-specific API.
#define USE_APP_LAB_RPC 0

// Where the weight comes from ----------------------------------------------
//
// WEIGHT_SOURCE_HX711   a load cell through an HX711 amplifier, two digital pins, the
//                       amplifier does the conversion and hands over raw counts
// WEIGHT_SOURCE_ANALOG  a load gauge that puts out a plain analog voltage, one analog
//                       pin, the board's own ADC does the conversion
//
// The bin we are building has the analog kind, so that is the default. The HX711 path is
// kept whole because it costs nothing to keep and it is the commoner part, so a
// replacement bought in a hurry will probably be one.
#define WEIGHT_SOURCE_HX711 0
#define WEIGHT_SOURCE_ANALOG 1

#define WEIGHT_SOURCE WEIGHT_SOURCE_HX711

// The analog load gauge ----------------------------------------------------
//
// NEEDS_HARDWARE_CHECK: which analog pin does the gauge's output go to? A0 through A5 on
// the UNO Q's header. Nothing else in the sketch names a pin.
#define ANALOG_WEIGHT_PIN A0

// The ADC resolution to ask the core for, in bits. The UNO Q's STM32U585 converter does
// 12 bits, and the core's analogReadResolution takes the number and scales for it. Asking
// for more than the hardware has costs nothing and gains nothing, so 12 is the answer
// here rather than a bigger number that would only be padded with zeroes.
//
// NEEDS_HARDWARE_CHECK: confirm on the board that analogReadResolution(12) sticks, by
// checking that `calibrate` reports counts above 1023. If it reports 0 to 1023 the core
// fell back to 10 bits, which is not fatal: take the two calibration points again at
// whatever resolution it gives and the arithmetic below still works.
#define ANALOG_READ_BITS 12

// How many readings to average per reported value. The gauge is noisy in a way the HX711
// is not, because there is no instrumentation amplifier in front of it, so eight samples
// are averaged here. Eight reads take well under a millisecond and the loop reports every
// 50 ms, so this costs nothing anybody can see.
#define ANALOG_AVERAGE_OF 8

// Two-point linear calibration, from the procedure in hardware/README.md section 5.
//
//   grams = (counts - ANALOG_ZERO_COUNTS) / ANALOG_COUNTS_PER_GRAM
//
// ANALOG_ZERO_COUNTS is what the empty bin reads. ANALOG_COUNTS_PER_GRAM is how much the
// reading moves per gram, found by putting a known mass in and dividing the change by it.
// Both are placeholders and the bin reads nonsense until they are measured.
//
// NEEDS_HARDWARE_CHECK: run `calibrate` twice, empty and with a known mass, and put the
// two numbers here.
#define ANALOG_ZERO_COUNTS 0.0f
#define ANALOG_COUNTS_PER_GRAM 1.0f

// Load cell amplifier ------------------------------------------------------
//
// Only read when WEIGHT_SOURCE is WEIGHT_SOURCE_HX711.
//
// NEEDS_HARDWARE_CHECK: which two pins is the HX711 wired to? Any two digital pins
// work, the library bit-bangs the protocol. DT is the data line out of the amplifier,
// SCK is the clock the board drives.
#define HX711_DT_PIN 2
#define HX711_SCK_PIN 3

// The bin sits on two bar load cells, each behind its own HX711. Both are read and the
// counts are added, so the plate weighs the same wherever the item lands. Set
// HX711_COUNT to 1 for a single amplifier and the second pair is ignored.
#define HX711_COUNT 2
#define HX711_DT2_PIN 4
#define HX711_SCK2_PIN 5

// NEEDS_HARDWARE_CHECK: does the breakout run at 10 or at 80 samples per second? Most
// HX711 breakouts tie the RATE pin low, which is 10 SPS, and the firmware contract asks
// for 10 to 20 Hz. 10 SPS meets the contract at its floor. Pulling RATE high gives 80
// SPS and a much better step detection. If the board has the RATE pad, tie it to VCC
// and set this to 80.
#define HX711_SPS 10

// Grams per raw count, found by the calibration in hardware/README.md. It is a divisor:
// grams = (raw - offset) / HX711_CALIBRATION. The value here is a placeholder, and the
// bin reads nonsense until it is replaced with the measured one.
// NEEDS_HARDWARE_CHECK: run the calibration and put the number here.
#define HX711_CALIBRATION 420.0f

// How many raw readings to average per reported value. One is fastest and noisiest, and
// the backend does all the filtering anyway, so one is the right answer here.
#define HX711_AVERAGE_OF 1

// How often the MCU reports a weight, in milliseconds. 50 ms is 20 Hz, the top of the
// contract's range. With a 10 SPS amplifier the sketch reports the last value it got,
// so the wire stays at 20 Hz while the scale updates at 10.
#define WEIGHT_PERIOD_MS 50

// Display ------------------------------------------------------------------
//
// NEEDS_HARDWARE_CHECK: which pins carry CS, DC and RST to the panel? MOSI and SCK go
// to the board's hardware SPI pins, which the library finds on its own. RST may be
// wired to the board's reset line instead, in which case set it to -1.
#define TFT_CS_PIN 10
#define TFT_DC_PIN 9
#define TFT_RST_PIN 8

// Portrait, 240 wide by 320 tall. Rotation 0 is portrait on both drivers.
#define TFT_WIDTH 240
#define TFT_HEIGHT 320
#define TFT_ROTATION 0

// NEEDS_HARDWARE_CHECK: does the panel have a backlight pin that needs driving high?
// Many breakouts tie it to VCC. Set to -1 when there is nothing to drive.
#define TFT_BACKLIGHT_PIN -1

// Colours ------------------------------------------------------------------
//
// DESIGN.md section 7 gives these as hex. RGB565 keeps 5 bits of red, 6 of green and 5
// of blue, so the macro drops the low bits of each channel. The computed value is in
// the comment beside each one, which is what a reader needs when a colour looks wrong.
#define RGB565(r, g, b) ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))

#define TONE_GREEN RGB565(0x1F, 0x7A, 0x4D)   // kept     #1F7A4D, 0x1BC9
#define TONE_AMBER RGB565(0xB7, 0x79, 0x1F)   // caution  #B7791F, 0xB3C3
#define TONE_RED RGB565(0xB3, 0x26, 0x1E)     // red-ink  #B3261E, 0xB123
#define TONE_PAPER RGB565(0xFB, 0xFC, 0xFA)   // paper    #FBFCFA, 0xFFFF, white once
                                              //          the low bits are dropped
#define COLOUR_INK RGB565(0x1A, 0x2B, 0x4C)   // ink      #1A2B4C, 0x1949
#define COLOUR_WHITE 0xFFFF

// Layout -------------------------------------------------------------------
//
// The built-in GFX font is 6 by 8 pixels at size 1 and scales by whole numbers. Line 1
// and line 2 run at size 2, which is 12 pixels per character, so the 20 characters the
// contract allows fill the 240 pixel width exactly. The big figure picks its own size
// so that whatever it is given fits the width, which lands on size 9 for a four
// character figure like -$20. That is the 72 pixel height DESIGN.md asks for.
#define LINE_TEXT_SIZE 2
#define LINE_CHAR_W (6 * LINE_TEXT_SIZE)
#define LINE_CHAR_H (8 * LINE_TEXT_SIZE)
#define SIDE_PADDING 8
#define LINE1_TOP 20
#define LINE2_BOTTOM 24
#define BIG_MAX_SIZE 9
#define BIG_MIN_SIZE 2

// Protocol -----------------------------------------------------------------

// Which port the JSON lines go out of when USE_APP_LAB_RPC is 0.
//
// Confirmed on this laptop, by reading the core's own zephyrSerial.h: the UNO Q's device
// tree has an arduino,router-serial node, so the core makes Serial the App Lab console
// and pushes the first hardware UART, the one on D0 and D1, to Serial1. So Serial1 below
// is right and Serial would be wrong.
//
// NEEDS_HARDWARE_CHECK: on the UNO Q, D0 and D1 are Serial1, and Arduino's manual says
// the router service owns the link to the Linux side and that nothing else may open
// /dev/ttyHS1. So the serial fallback on a UNO Q means a USB to serial adapter on D0
// and D1 going to the laptop, not a cable to the board's own Linux side. On a plain
// Arduino board with a USB port of its own, change this to Serial. On the UNO Q,
// Monitor is App Lab's console and is for printing, not for this protocol.
#define BIN_SERIAL Serial1

#define SERIAL_BAUD 115200
#define LINE_MAX 20  // characters in line 1 and line 2, from firmware_contract.md
#define BIG_MAX 7    // characters in the big figure, from firmware_contract.md

// No ping from the backend for this long means the bridge is gone and the screen says
// offline on its own. firmware_contract.md, last line.
#define OFFLINE_AFTER_MS 5000UL

#endif  // BIN_CONFIG_H
