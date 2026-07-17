#!/bin/sh

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"
API="http://127.0.0.1:7913"
EXIT_CODE=0

echo "=== $APP_NAME ==="

if [ -f "$APP_DIR/VERSION" ]; then
    echo "Package version: $(cat "$APP_DIR/VERSION")"
else
    echo "Package version: unknown"
fi

echo
echo "--- Process ---"

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"

    if [ -n "$PID" ] &&
        kill -0 "$PID" 2>/dev/null
    then
        echo "Status: RUNNING"
        echo "PID: $PID"
        echo -n "Command: "
        tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null
        echo
    else
        echo "Status: STALE PID FILE"
        EXIT_CODE=1
    fi
else
    echo "Status: STOPPED"
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
echo "--- Filament capabilities (read-only) ---"

if wget -qO- "$API/api/filament/capabilities?refresh=1"; then
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
        if grep -q 'ifs-spoolman-card' "$INDEX"; then
            echo "Card: installed"
        else
            echo "Card: not installed"
            EXIT_CODE=1
        fi

        if grep -q 'ifs-spoolman-layout' "$INDEX"; then
            echo "Layout: installed"
        else
            echo "Layout: not installed"
            EXIT_CODE=1
        fi
    else
        echo "Fluidd index.html: not found"
        EXIT_CODE=1
    fi
else
    echo "Moonraker: not found"
    EXIT_CODE=1
fi

echo
echo "--- Last events ---"

tail -n 10 "$APP_DIR/events.log" 2>/dev/null ||
    echo "events.log is empty or absent"

exit "$EXIT_CODE"
