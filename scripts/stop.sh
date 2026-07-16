#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "$APP_NAME не запущен."
    exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"

if [ -n "$PID" ] &&
    kill -0 "$PID" 2>/dev/null
then
    kill "$PID"

    i=0

    while kill -0 "$PID" 2>/dev/null &&
        [ "$i" -lt 20 ]
    do
        sleep 1
        i=$((i + 1))
    done

    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID" 2>/dev/null || true
    fi

    echo "$APP_NAME остановлен: PID $PID"
else
    echo "$APP_NAME: удалён устаревший PID-файл."
fi

rm -f "$PID_FILE"
