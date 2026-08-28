#!/bin/sh
set -eu

BRANCH="feature/gcode-3mf-ifs-preflight"
BASE="https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/$BRANCH/experimental/gcode_3mf"
DIR="/tmp/ad5x_ifs_3mf_7913"
PID_FILE="$DIR/test.pid"
LOG_FILE="$DIR/test.log"
RUNTIME="/usr/data/config/mod_data/ifs_spoolman"
STOP="$RUNTIME/stop.sh"
START="$RUNTIME/start.sh"
PYTHON="/root/moonraker-env/bin/python3"

[ -x "$STOP" ] || { echo "release runtime stop.sh not found: $STOP" >&2; exit 1; }
[ -x "$START" ] || { echo "release runtime start.sh not found: $START" >&2; exit 1; }

mkdir -p "$DIR"

pid_is_combined() {
    pid="$1"
    [ -r "/proc/$pid/cmdline" ] || return 1
    cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
    case "$cmd" in
        *combined_7913.py*) return 0 ;;
    esac
    return 1
}

stop_existing_combined() {
    [ -f "$PID_FILE" ] || return 0
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && pid_is_combined "$pid"; then
        kill "$pid" 2>/dev/null || true
        i=0
        while pid_is_combined "$pid" && [ "$i" -lt 10 ]; do
            sleep 1
            i=$((i + 1))
        done
        pid_is_combined "$pid" && kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
}

# Stop the previous experimental owner before replacing its on-disk files.
stop_existing_combined

for file in combined_7913.py combined.html inspect.py; do
    rm -f "$DIR/$file"
    wget -qO "$DIR/$file" "$BASE/$file?cb=$(date +%s)"
done
chmod +x "$DIR/combined_7913.py" "$DIR/inspect.py"

# Retire the old standalone 7914 experiment if it still exists.
if [ -f /tmp/gcode_3mf_exp.pid ]; then
    old="$(cat /tmp/gcode_3mf_exp.pid 2>/dev/null || true)"
    [ -n "$old" ] && kill "$old" 2>/dev/null || true
    rm -f /tmp/gcode_3mf_exp.pid
fi

# Exactly one IFS runtime owner at a time. This is harmless when the release
# runtime is already stopped because the combined host owned port 7913.
"$STOP"

cleanup_failed() {
    echo "Experimental 7913 host failed; restoring release IFS." >&2
    if [ -f "$PID_FILE" ]; then
        pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        [ -n "$pid" ] && pid_is_combined "$pid" && kill "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    "$START" || true
    tail -n 80 "$LOG_FILE" 2>/dev/null || true
}
trap cleanup_failed HUP INT TERM

chroot /usr/data/.mod/.zmod "$PYTHON" "$DIR/combined_7913.py" >"$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" >"$PID_FILE"

sleep 2
if ! pid_is_combined "$pid"; then
    cleanup_failed
    exit 1
fi

if ! wget -qO /tmp/ad5x_ifs_3mf_7913.health http://127.0.0.1:7913/api/3mf/health; then
    cleanup_failed
    exit 1
fi

trap - HUP INT TERM

echo "=== EXPERIMENTAL 7913 HEALTH ==="
cat /tmp/ad5x_ifs_3mf_7913.health
echo
echo "PID=$pid"
echo "LOG=$LOG_FILE"
echo "Open: http://PRINTER_IP:7913/"
