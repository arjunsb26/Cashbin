#!/usr/bin/env bash
# Two-point calibration of the analog load gauge, driven from the laptop over the cable,
# while the Cashbin app keeps running on the board. Run it from Git Bash in the repo root.
#
#   hardware/uno_q/calibrate.sh read                 print the raw counts right now
#   hardware/uno_q/calibrate.sh apply EMPTY LOADED MASS_G
#                                                    write the two numbers into the sketch on
#                                                    the board and restart the app, which
#                                                    recompiles and flashes it
#   hardware/uno_q/calibrate.sh tare                 zero the scale without a re-flash
#   hardware/uno_q/calibrate.sh panel ili9341|st7789 pick the display driver and re-flash
#
# The procedure, from hardware/README.md section 5: with the bin empty and settled, `read`
# and write the counts down as EMPTY. Put a known mass in, `read` again, that is LOADED.
# Then `apply EMPTY LOADED MASS_G`. The re-flash takes about two minutes.

set -euo pipefail

ADB="${ADB:-C:/Users/nisni/AppData/Local/Arduino15/packages/arduino/tools/adb/32.0.0/adb.exe}"
APP=/home/arduino/ArduinoApps/cashbin
CONTAINER=cashbin-main-1

rpc() {
  "$ADB" shell "timeout 20 docker exec $CONTAINER python -c \"from arduino.app_utils import Bridge; print(Bridge.call('$1', timeout=5))\"" | tr -d '\r'
}

case "${1:-}" in
  read)
    echo "counts $(rpc calibrate)"
    echo "grams  $(rpc read_grams)"
    ;;
  tare)
    rpc tare >/dev/null && echo "tared"
    ;;
  apply)
    empty="${2:?EMPTY counts}"; loaded="${3:?LOADED counts}"; mass="${4:?known mass in grams}"
    per_gram=$(python -c "print(round(($loaded - $empty) / $mass, 6))")
    echo "zero $empty counts, $per_gram counts per gram"
    "$ADB" shell "sed -i 's/^#define ANALOG_ZERO_COUNTS .*/#define ANALOG_ZERO_COUNTS ${empty}f/; s/^#define ANALOG_COUNTS_PER_GRAM .*/#define ANALOG_COUNTS_PER_GRAM ${per_gram}f/' $APP/sketch/bin_config.h && grep -n 'ANALOG_ZERO_COUNTS\|ANALOG_COUNTS_PER_GRAM' $APP/sketch/bin_config.h | grep define"
    echo "restarting the app, which recompiles and flashes the sketch"
    "$ADB" shell "arduino-app-cli app restart $APP 2>&1 | tail -2"
    ;;
  panel)
    driver="${2:?ili9341 or st7789}"
    case "$driver" in
      ili9341) ili=1; st=0 ;;
      st7789) ili=0; st=1 ;;
      *) echo "panel is ili9341 or st7789" >&2; exit 64 ;;
    esac
    "$ADB" shell "sed -i 's/^#define USE_ILI9341 .*/#define USE_ILI9341 $ili/; s/^#define USE_ST7789 .*/#define USE_ST7789 $st/' $APP/sketch/bin_config.h && grep -n 'USE_ILI9341\|USE_ST7789' $APP/sketch/bin_config.h | grep define"
    "$ADB" shell "arduino-app-cli app restart $APP 2>&1 | tail -2"
    ;;
  *)
    sed -n '2,15p' "$0"
    exit 64
    ;;
esac
