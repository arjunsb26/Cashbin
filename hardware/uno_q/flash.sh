#!/usr/bin/env bash
# Compile the bin sketch, put it on the UNO Q, and watch the first JSON lines.
#
#   ./hardware/uno_q/flash.sh
#   ./hardware/uno_q/flash.sh --port /dev/ttyACM0
#   ./hardware/uno_q/flash.sh --compile-only
#
# Compile only needs no board, which is how the sketch was proven before the board
# arrived. Everything else needs the board plugged in with USB-C.

set -euo pipefail

FQBN="arduino:zephyr:unoq"
SKETCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sketch"
BAUD=115200

PORT=""
MONITOR_SECONDS=10
COMPILE_ONLY=0
NO_MONITOR=0

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --seconds) MONITOR_SECONDS="$2"; shift 2 ;;
    --compile-only) COMPILE_ONLY=1; shift ;;
    --no-monitor) NO_MONITOR=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
  esac
done

# Where arduino-cli is ----------------------------------------------------------

if command -v arduino-cli >/dev/null 2>&1; then
  CLI="$(command -v arduino-cli)"
elif [ -x "/d/codering/tools/arduino-cli/arduino-cli.exe" ]; then
  CLI="/d/codering/tools/arduino-cli/arduino-cli.exe"
else
  echo "arduino-cli is not installed. See hardware/README.md, section 1." >&2
  exit 1
fi

echo "arduino-cli  $CLI"
"$CLI" version
echo

# Which display the sketch is built for, so the log says it out loud --------------

CONFIG="$SKETCH_DIR/bin_config.h"
if grep -q '#define USE_ILI9341 1' "$CONFIG"; then
  DRIVER="ILI9341"
elif grep -q '#define USE_ST7789 1' "$CONFIG"; then
  DRIVER="ST7789"
else
  DRIVER="none, and the build will stop"
fi
if grep -q '#define USE_APP_LAB_RPC 1' "$CONFIG"; then
  LINK="the App Lab router bridge"
else
  LINK="serial JSON lines"
fi
echo "display driver  $DRIVER"
echo "host link       $LINK"
echo

# Compile -------------------------------------------------------------------------

echo "compiling $SKETCH_DIR"
if ! "$CLI" compile --fqbn "$FQBN" "$SKETCH_DIR"; then
  echo "the sketch did not compile, so nothing was uploaded" >&2
  exit 1
fi
echo

if [ "$COMPILE_ONLY" = "1" ]; then
  echo "compile only, stopping here"
  exit 0
fi

# Find the board ------------------------------------------------------------------

if [ -z "$PORT" ]; then
  # Named first: the core recognises the board and tells us the FQBN. Then by the
  # UNO Q's USB identity, from `arduino-cli board details`.
  PORT="$("$CLI" board list --format json 2>/dev/null | python3 -c '
import json, sys
try:
    doc = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ports = doc if isinstance(doc, list) else doc.get("detected_ports", [])
want = "arduino:zephyr:unoq"
for p in ports:
    for b in p.get("matching_boards") or []:
        if b.get("fqbn") == want:
            print(p["port"]["address"]); sys.exit(0)
for p in ports:
    props = p.get("port", {}).get("properties") or {}
    if "2341" in str(props.get("vid", "")) and "0078" in str(props.get("pid", "")):
        print(p["port"]["address"]); sys.exit(0)
' || true)"
fi

if [ -z "$PORT" ]; then
  cat <<'EOF'

No UNO Q found on a port. The sketch compiled, so this is a cable or a mode
problem, not a code problem. Three things to try, in order:

  1. USB-C into the board's own port, not a hub, and wait ten seconds for the
     Linux side to finish booting. Then run this script again.
  2. Pass the port by hand once you know it:
       --port /dev/ttyACM0
     `arduino-cli board list` shows every port this machine has.
  3. On the UNO Q the Linux side owns the USB port, so the documented way in is
     the board itself. See hardware/uno_q/board_linux_setup.md, which has the
     shell, the wifi and the bridge.
EOF
  exit 2
fi

echo "board on $PORT"
echo

# Upload ---------------------------------------------------------------------------

echo "uploading"
if ! "$CLI" upload -p "$PORT" --fqbn "$FQBN" "$SKETCH_DIR"; then
  echo "the upload failed on $PORT" >&2
  exit 1
fi
echo "uploaded"
echo

if [ "$NO_MONITOR" = "1" ]; then
  exit 0
fi

# Watch ------------------------------------------------------------------------------

cat <<EOF
watching $PORT for $MONITOR_SECONDS seconds at $BAUD baud

What you want to see is one JSON object per line, about twenty a second:
  {"t":123456,"g":0.00}

Nothing at all is expected in two cases, and neither is a fault:
  - USE_APP_LAB_RPC is 1, so the weights go over the router bridge, not a wire.
  - USE_APP_LAB_RPC is 0, and the lines leave on D0 and D1, which need a USB to
    serial adapter of their own. hardware/README.md section 9 has the wiring.

EOF

LOG="$(mktemp)"
"$CLI" monitor -p "$PORT" --fqbn "$FQBN" -c "baudrate=$BAUD" >"$LOG" 2>&1 &
MON_PID=$!
sleep "$MONITOR_SECONDS"
kill "$MON_PID" 2>/dev/null || true
wait "$MON_PID" 2>/dev/null || true

if [ -s "$LOG" ]; then
  echo "--- first 20 lines ---"
  head -n 20 "$LOG"
  echo "--- $(wc -l <"$LOG" | tr -d ' ') lines in $MONITOR_SECONDS seconds ---"
else
  echo "nothing arrived on $PORT, which the two notes above may explain"
fi
rm -f "$LOG"
