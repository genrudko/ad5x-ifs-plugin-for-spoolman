#!/bin/sh
set -eu

APP_NAME="AD5X IFS Manager"
APP_DIR="/opt/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"
LOG_FILE="$APP_DIR/ifs_spoolman.log"
PYTHON="/root/moonraker-env/bin/python3"
PROGRAM="$APP_DIR/ifs_spoolman_writer.py"

if [ -x "$APP_DIR/install_fluidd_card.sh" ]; then
    "$APP_DIR/install_fluidd_card.sh" \
        >>"$APP_DIR/fluidd_card.log" 2>&1 || true
fi

i=0
while [ "$i" -lt 60 ]; do
    if wget -qO- http://127.0.0.1:7125/server/info >/dev/null 2>&1; then
        break
    fi
    i=$((i + 1))
    sleep 1
done

if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "$APP_NAME уже запущен: PID $OLD_PID"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

[ -x "$PYTHON" ] || { echo "$APP_NAME: не найден Python: $PYTHON"; exit 1; }
[ -f "$PROGRAM" ] || { echo "$APP_NAME: не найден runtime: $PROGRAM"; exit 1; }

nohup "$PYTHON" "$PROGRAM" >>"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" >"$PID_FILE"
sleep 1

if kill -0 "$NEW_PID" 2>/dev/null; then
    echo "$APP_NAME запущен: PID $NEW_PID"
    exit 0
fi

echo "$APP_NAME не запустился."
tail -n 50 "$LOG_FILE" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1
