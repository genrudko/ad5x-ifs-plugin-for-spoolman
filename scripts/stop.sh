#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"

pid_is_plugin() {
    PID="$1"
    [ -r "/proc/$PID/cmdline" ] || return 1
    CMD="$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null || true)"
    case "$CMD" in
        *ifs_spoolman.py*) return 0 ;;
    esac
    return 1
}

PIDS=""

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$PID" ] && pid_is_plugin "$PID"; then
        PIDS="$PID"
    fi
fi

for P in /proc/[0-9]*; do
    PID="${P##*/}"
    pid_is_plugin "$PID" || continue
    case " $PIDS " in
        *" $PID "*) ;;
        *) PIDS="$PIDS $PID" ;;
    esac
done

if [ -z "$(printf '%s' "$PIDS" | tr -d ' ')" ]; then
    rm -f "$PID_FILE"
    echo "$APP_NAME не запущен."
    exit 0
fi

for PID in $PIDS; do
    kill "$PID" 2>/dev/null || true
done

for PID in $PIDS; do
    i=0
    while pid_is_plugin "$PID" && [ "$i" -lt 20 ]; do
        sleep 1
        i=$((i + 1))
    done

    if pid_is_plugin "$PID"; then
        kill -9 "$PID" 2>/dev/null || true
    fi
done

rm -f "$PID_FILE"
echo "$APP_NAME остановлен: PID$(printf ' %s' $PIDS)"
