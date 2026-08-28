#!/bin/sh
set -eu
DIR="/tmp/ad5x_ifs_3mf_7913"
PID_FILE="$DIR/test.pid"
START="/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman/scripts/start.sh"

if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null || true
        i=0
        while kill -0 "$pid" 2>/dev/null && [ "$i" -lt 10 ]; do
            sleep 1
            i=$((i + 1))
        done
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
fi

"$START"
sleep 1

echo "=== RELEASE IFS HEALTH ==="
wget -qO- http://127.0.0.1:7913/api/health || true
echo
