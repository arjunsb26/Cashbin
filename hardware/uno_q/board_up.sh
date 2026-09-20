#!/usr/bin/env bash
# Start the whole bin: the bridge that carries weights and screens, and the webcam that
# watches the bin. Runs on the board's own Debian, not on the laptop.
#
#   ./board_up.sh 192.168.137.1     the laptop's address, which wins over board.env
#   ./board_up.sh                   reads LAPTOP_IP from board.env
#   ./board_up.sh --no-webcam       the bridge only
#
# Each program gets a loop that restarts it if it exits, because a dropped socket or an
# unplugged camera should not end the demo. Both already reconnect on their own, so the
# loop is only for the case where the process dies outright.
#
# Logs go to ~/binbooks/logs/. Stop everything with ./board_down.sh.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/board.env"

# Settings, weakest first: the defaults here, then board.env, then the argument.
LAPTOP_IP=""
LAPTOP_PORT=8000
CAMERA_INDEX=0
BIN_SOURCE=bridge
CAMERA_FPS=8
BIN_HOME="$HERE"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

WANT_WEBCAM=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-webcam) WANT_WEBCAM=0; shift ;;
    --no-bridge) WANT_BRIDGE=0; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) LAPTOP_IP="$1"; shift ;;
  esac
done
WANT_BRIDGE="${WANT_BRIDGE:-1}"

if [ -z "$LAPTOP_IP" ]; then
  echo "No laptop address. Pass one, or put LAPTOP_IP in $ENV_FILE:" >&2
  echo "  ./board_up.sh 192.168.137.1" >&2
  echo "Run hardware\\find_laptop_ip.ps1 on the laptop to find it." >&2
  exit 64
fi

# Which python. A virtual environment at ~/binenv wins, because section 4 of
# board_linux_setup.md makes one when Debian refuses a plain pip install.
if [ -x "$HOME/binenv/bin/python3" ]; then
  PY="$HOME/binenv/bin/python3"
else
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "python3 is not installed. See board_linux_setup.md, section 4." >&2
  exit 1
fi

RUN_DIR="$HOME/binbooks"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"

BRIDGE_URL="ws://$LAPTOP_IP:$LAPTOP_PORT/ws/bin"
PHONE_URL="ws://$LAPTOP_IP:$LAPTOP_PORT/ws/phone"

# One supervised program. The loop is the restart, the pid file is how board_down finds
# it, and the log is the only place anybody looks when the demo misbehaves.
start_one() {
  local name="$1"; shift
  local script="$1"; shift
  local pidfile="$RUN_DIR/$name.pid"
  local log="$LOG_DIR/$name.log"

  if [ ! -f "$script" ]; then
    echo "missing: $script" >&2
    echo "  copy it over, see board_linux_setup.md sections 5 and 10" >&2
    return 1
  fi

  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    echo "$name is already running as $(cat "$pidfile"), leaving it alone"
    return 0
  fi

  rm -f "$pidfile"

  # The supervisor is a subshell in the background, under nohup so that closing the SSH
  # window does not take the bin down with it. It writes its own pid rather than letting
  # the caller use $!, because the two are not always the same process, and it kills the
  # program under it on the way out so board_down.sh never leaves a python holding the
  # camera.
  nohup bash -c '
    name="$1"; py="$2"; script="$3"; log="$4"; pidfile="$5"; shift 5
    echo $$ >"$pidfile"
    child=""
    stop() {
      [ -n "$child" ] && kill -TERM "$child" 2>/dev/null
      echo "--- $(date "+%Y-%m-%d %H:%M:%S") $name asked to stop ---" >>"$log"
      rm -f "$pidfile"
      exit 0
    }
    trap stop TERM INT HUP
    while true; do
      echo "--- $(date "+%Y-%m-%d %H:%M:%S") starting $name ---" >>"$log"
      "$py" "$script" "$@" >>"$log" 2>&1 &
      child=$!
      wait "$child"
      code=$?
      child=""
      echo "--- $(date "+%Y-%m-%d %H:%M:%S") $name exited $code ---" >>"$log"
      [ "$code" = "0" ] && break
      echo "--- restarting in 2 s ---" >>"$log"
      sleep 2
    done
    rm -f "$pidfile"
  ' _ "$name" "$PY" "$script" "$log" "$pidfile" "$@" >/dev/null 2>&1 &

  # The supervisor writes the pid file itself, so wait a moment for it rather than
  # reporting a number that might belong to something else.
  for _ in $(seq 1 20); do
    [ -f "$pidfile" ] && break
    sleep 0.1
  done
  if [ -f "$pidfile" ]; then
    echo "$name started as $(cat "$pidfile"), logging to $log"
  else
    echo "$name did not come up, look in $log" >&2
    return 1
  fi
}

echo "laptop      $LAPTOP_IP:$LAPTOP_PORT"
echo "python      $PY"
echo "logs        $LOG_DIR"
echo

if [ "$WANT_BRIDGE" = "1" ]; then
  start_one bridge "$BIN_HOME/bridge.py" \
    --url "$BRIDGE_URL" --source "$BIN_SOURCE"
fi

if [ "$WANT_WEBCAM" = "1" ]; then
  start_one webcam "$BIN_HOME/webcam_client.py" \
    --url "$PHONE_URL" --camera "$CAMERA_INDEX" --fps "$CAMERA_FPS"
fi

echo
echo "Watch either one:"
echo "  tail -f $LOG_DIR/bridge.log"
echo "  tail -f $LOG_DIR/webcam.log"
echo "Stop both:"
echo "  $HERE/board_down.sh"
