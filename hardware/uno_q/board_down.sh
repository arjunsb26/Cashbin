#!/usr/bin/env bash
# Stop what board_up.sh started. Runs on the board's own Debian.
#
#   ./board_down.sh            stop both
#   ./board_down.sh bridge     stop one
#
# It asks the supervisor to stop, and the supervisor kills the program under it on its way
# out. Killing only the supervisor would leave the python holding the camera, and the next
# board_up.sh would then start a second one that fights the first for it.

set -uo pipefail

RUN_DIR="$HOME/binbooks"
NAMES=("bridge" "webcam")
if [ $# -gt 0 ]; then
  NAMES=("$@")
fi

stopped=0

for name in "${NAMES[@]}"; do
  pidfile="$RUN_DIR/$name.pid"
  if [ ! -f "$pidfile" ]; then
    echo "$name was not running"
    continue
  fi
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    echo "$name was not running, clearing a stale pid file"
    rm -f "$pidfile"
    continue
  fi

  # TERM reaches the supervisor's trap, which kills the program under it and removes the
  # pid file itself.
  kill -TERM "$pid" 2>/dev/null || true

  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "$name did not stop when asked, so it is being killed"
    kill -KILL "$pid" 2>/dev/null || true
  fi

  # The supervisor normally takes the python with it. If it was killed outright it could
  # not, so sweep up anything still running from that script.
  case "$name" in
    bridge) leftover="bridge.py" ;;
    webcam) leftover="webcam_client.py" ;;
    *) leftover="" ;;
  esac
  if [ -n "$leftover" ] && command -v pkill >/dev/null 2>&1; then
    pkill -TERM -f "$leftover" 2>/dev/null || true
  fi

  rm -f "$pidfile"
  echo "$name stopped"
  stopped=$((stopped + 1))
done

# A camera left open by a process nobody has a pid for is the one failure that survives a
# restart, so say how to find it rather than leaving somebody guessing.
if [ "$stopped" = "0" ]; then
  echo
  echo "Nothing was running. If the camera is still busy, something started outside these"
  echo "scripts is holding it. Find it with:"
  echo "  fuser -v /dev/video*"
  echo "  pgrep -af 'bridge.py|webcam_client.py'"
fi
