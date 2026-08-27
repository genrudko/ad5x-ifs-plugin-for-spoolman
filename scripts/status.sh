#!/bin/sh

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"
API="http://127.0.0.1:7913"
EXIT_CODE=0

pid_is_plugin() {
    PID="$1"
    [ -r "/proc/$PID/cmdline" ] || return 1
    CMD="$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null || true)"
    case "$CMD" in
        *ifs_spoolman.py*) return 0 ;;
    esac
    return 1
}

find_plugin_pids() {
    for P in /proc/[0-9]*; do
        PID="${P##*/}"
        pid_is_plugin "$PID" && echo "$PID"
    done
}

echo "=== $APP_NAME ==="

if [ -f "$APP_DIR/VERSION" ]; then
    echo "Package version: $(cat "$APP_DIR/VERSION")"
else
    echo "Package version: unknown"
    EXIT_CODE=1
fi

echo
echo "--- Z-Mod power-on hook ---"
if [ -x "$APP_DIR/power_on_hook.sh" ] && "$APP_DIR/power_on_hook.sh" check >/dev/null 2>&1; then
    echo "Autostart: installed"
else
    echo "Autostart: MISSING"
    EXIT_CODE=1
fi

echo
echo "--- Process ---"
TRACKED_PID=""
if [ -f "$PID_FILE" ]; then
    TRACKED_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
fi

RUNNING_PIDS="$(find_plugin_pids 2>/dev/null || true)"

if [ -n "$TRACKED_PID" ] && pid_is_plugin "$TRACKED_PID"; then
    echo "Status: RUNNING"
    echo "PID: $TRACKED_PID"
    echo -n "Command: "
    tr '\0' ' ' <"/proc/$TRACKED_PID/cmdline" 2>/dev/null
    echo
else
    if [ -f "$PID_FILE" ]; then
        echo "PID file: stale or points to a non-plugin process"
        EXIT_CODE=1
    fi

    if [ -n "$RUNNING_PIDS" ]; then
        echo "Status: RUNNING WITHOUT VALID PID FILE"
        echo "Detected PID(s): $(printf '%s' "$RUNNING_PIDS" | tr '\n' ' ')"
        EXIT_CODE=1
    else
        echo "Status: STOPPED"
        EXIT_CODE=1
    fi
fi

PID_COUNT="$(printf '%s\n' "$RUNNING_PIDS" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "${PID_COUNT:-0}" -gt 1 ] 2>/dev/null; then
    echo "WARNING: multiple backend processes detected: $PID_COUNT"
    EXIT_CODE=1
fi

echo
echo "--- API health ---"
if wget -qO- "$API/api/health"; then
    echo
else
    echo "UNAVAILABLE"
    EXIT_CODE=1
fi

echo
echo "--- API status ---"
if wget -qO- "$API/api/status"; then
    echo
else
    echo "UNAVAILABLE"
    EXIT_CODE=1
fi

echo
echo "--- Fluidd integration ---"
MOON_PID=""
for P in /proc/[0-9]*; do
    [ -r "$P/cmdline" ] || continue
    CMD="$(tr '\0' ' ' <"$P/cmdline" 2>/dev/null || true)"
    case "$CMD" in
        *moonraker.py*)
            MOON_PID="${P##*/}"
            break
            ;;
    esac
done

if [ -n "$MOON_PID" ]; then
    INDEX="/proc/$MOON_PID/root/root/fluidd/index.html"
    if [ -f "$INDEX" ]; then
        for PART in card layout dashboard selection; do
            if grep -q "ifs-spoolman-$PART" "$INDEX"; then
                echo "$PART: installed"
            else
                echo "$PART: not installed"
                EXIT_CODE=1
            fi
        done
    else
        echo "Fluidd index.html: not found"
        EXIT_CODE=1
    fi
else
    echo "Moonraker: not found"
    EXIT_CODE=1
fi

echo
echo "--- Last boot messages ---"
tail -n 20 "$APP_DIR/boot.log" 2>/dev/null ||
    echo "boot.log is empty or absent"

echo
echo "--- Last events ---"
tail -n 10 "$APP_DIR/events.log" 2>/dev/null ||
    echo "events.log is empty or absent"

exit "$EXIT_CODE"
