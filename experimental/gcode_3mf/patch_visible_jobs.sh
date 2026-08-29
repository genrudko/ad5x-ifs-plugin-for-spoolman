#!/bin/sh
set -eu

REV="ed9c0b91ed83bf6cb4f46761c963fbad8617f660"
BASE="https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/$REV/experimental/gcode_3mf"
CHROOT=/usr/data/.mod/.zmod
RUNTIME_HOST=/usr/data/config/mod_data/gcode_3mf_exp/gcode_3mf.py
RUNTIME_CHROOT=/opt/config/mod_data/gcode_3mf_exp/gcode_3mf.py
RUNTIME_DIR=/usr/data/config/mod_data/gcode_3mf_exp
TMP_HOST="$RUNTIME_DIR/gcode_3mf.py.visible-jobs.new"
TMP_CHROOT=/opt/config/mod_data/gcode_3mf_exp/gcode_3mf.py.visible-jobs.new
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="$RUNTIME_DIR/gcode_3mf.py.pre-visible-jobs-$TS"
INFO=/tmp/gcode3mf-visible-jobs-info
STATE=/tmp/gcode3mf-visible-jobs-state

[ -d "$CHROOT" ] || { echo "Z-Mod chroot not found: $CHROOT" >&2; exit 1; }
[ -f "$RUNTIME_HOST" ] || { echo "GCode3MF runtime not found: $RUNTIME_HOST" >&2; exit 1; }

# Never restart Moonraker as part of this patch while a job is active.  The
# component itself is print-path code, so installation belongs between jobs.
if wget -qO "$STATE" \
    'http://127.0.0.1:7125/printer/objects/query?print_stats' 2>/dev/null; then
    PRINT_STATE="$(chroot "$CHROOT" /root/moonraker-env/bin/python3 - "$STATE" <<'PY'
import json, sys
try:
    data=json.load(open(sys.argv[1]))
    print(data['result']['status']['print_stats'].get('state','unknown'))
except Exception:
    print('unknown')
PY
)"
    echo "print_state=$PRINT_STATE"
    case "$PRINT_STATE" in
        printing|paused)
            echo "Refusing to patch while a print is active." >&2
            exit 2
            ;;
    esac
fi

cp -p "$RUNTIME_HOST" "$BACKUP"
echo "backup=$BACKUP"
rm -f "$TMP_HOST"

wget -qO "$TMP_HOST" "$BASE/moonraker_gcode_3mf.py?cb=$(date +%s)"
chmod 644 "$TMP_HOST"

# Verify this is the intended lifecycle patch, not a stale raw response.
grep -q '_archive_source_after_upload' "$TMP_HOST"
grep -q 'gcode_relative' "$TMP_HOST"
grep -q 'GCode3MF metadata ready gcode=' "$TMP_HOST"

# Compile before replacing the live runtime.
chroot "$CHROOT" /root/moonraker-env/bin/python3 -m py_compile "$TMP_CHROOT"
mv "$TMP_HOST" "$RUNTIME_HOST"

rollback() {
    echo "Visible-jobs patch failed; restoring previous runtime." >&2
    cp -p "$BACKUP" "$RUNTIME_HOST" || true
    chroot "$CHROOT" /etc/init.d/S65moonraker restart || true
}

trap rollback HUP INT TERM

echo "=== RESTART MOONRAKER ==="
chroot "$CHROOT" /etc/init.d/S65moonraker restart

OK=0
i=0
while [ "$i" -lt 30 ]; do
    if wget -qO "$INFO" 'http://127.0.0.1:7125/server/info' 2>/dev/null; then
        KLIPPY_STATE="$(chroot "$CHROOT" /root/moonraker-env/bin/python3 - "$INFO" <<'PY'
import json, sys
try:
    data=json.load(open(sys.argv[1]))['result']
    print(data.get('klippy_state',''))
except Exception:
    print('')
PY
)"
        echo "[$i] klippy_state=$KLIPPY_STATE"
        if [ "$KLIPPY_STATE" = "ready" ]; then
            OK=1
            break
        fi
    else
        echo "[$i] Moonraker not listening yet"
    fi
    sleep 2
    i=$((i + 1))
done

if [ "$OK" -ne 1 ]; then
    rollback
    trap - HUP INT TERM
    exit 1
fi

if ! grep -q 'GCode3MF experimental start interceptor installed' \
    /usr/data/logs/moonraker.log 2>/dev/null; then
    echo "Moonraker is ready but GCode3MF load marker is missing." >&2
    rollback
    trap - HUP INT TERM
    exit 1
fi

trap - HUP INT TERM

echo
echo "=== PATCH VERIFY ==="
grep -n -E '_ensure_metadata|_archive_source_after_upload|gcode_relative' \
    "$RUNTIME_HOST" | head -n 20

echo
echo "GCode3MF visible-jobs patch installed."
echo "Source 3MF will be archived only after a successful direct print start."
echo "Canonical extracted G-code will remain visible in Fluidd Jobs."
