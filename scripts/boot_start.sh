#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/opt/config/mod_data/ifs_spoolman"
PID_FILE="$APP_DIR/ifs_spoolman.pid"
LOG_FILE="$APP_DIR/ifs_spoolman.log"
PYTHON="/root/moonraker-env/bin/python3"
PROGRAM="$APP_DIR/ifs_spoolman.py"
CONFIG_FILE="$APP_DIR/config.json"
FLUIDD_NATIVE_MARKER="/root/fluidd/ad5x_ifs_native.json"

pid_is_plugin() {
    PID="$1"
    [ -r "/proc/$PID/cmdline" ] || return 1
    CMD="$(tr '\0' ' ' <"/proc/$PID/cmdline" 2>/dev/null || true)"
    case "$CMD" in
        *ifs_spoolman.py*) return 0 ;;
    esac
    return 1
}

find_running_plugin() {
    for P in /proc/[0-9]*; do
        PID="${P##*/}"
        if pid_is_plugin "$PID"; then
            echo "$PID"
            return 0
        fi
    done
    return 1
}

fluidd_enabled() {
    # Missing config or missing key keeps the documented default: enabled.
    [ -f "$CONFIG_FILE" ] || return 0
    if grep -Eq '"fluidd_integration"[[:space:]]*:[[:space:]]*false([[:space:],}]|$)' "$CONFIG_FILE"; then
        return 1
    fi
    return 0
}

if fluidd_enabled; then
    if [ -f "$FLUIDD_NATIVE_MARKER" ]; then
        # A compatibility build contains the IFS card as a real Fluidd Vue
        # component. Never add the legacy HTML/DOM scripts on top of it.
        echo "$APP_NAME: native Fluidd integration detected; legacy injection skipped." \
            >>"$APP_DIR/fluidd_card.log" 2>&1 || true
    elif [ -x "$APP_DIR/install_fluidd_card.sh" ]; then
        "$APP_DIR/install_fluidd_card.sh" \
            >>"$APP_DIR/fluidd_card.log" 2>&1 || true
    fi
else
    if [ -f "$FLUIDD_NATIVE_MARKER" ]; then
        echo "$APP_NAME: native Fluidd integration is installed; disable requires native Fluidd rollback." \
            >>"$APP_DIR/fluidd_card.log" 2>&1 || true
    elif [ -x "$APP_DIR/uninstall_fluidd_card.sh" ]; then
        "$APP_DIR/uninstall_fluidd_card.sh" \
            >>"$APP_DIR/fluidd_card.log" 2>&1 || true
    fi
fi

if [ -f "$PID_FILE" ]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"

    if [ -n "$OLD_PID" ] && pid_is_plugin "$OLD_PID"; then
        echo "$APP_NAME уже запущен: PID $OLD_PID"
        exit 0
    fi

    rm -f "$PID_FILE"
fi

RUNNING_PID="$(find_running_plugin 2>/dev/null || true)"
if [ -n "$RUNNING_PID" ]; then
    echo "$RUNNING_PID" >"$PID_FILE"
    echo "$APP_NAME уже запущен: PID $RUNNING_PID (PID-файл восстановлен)"
    exit 0
fi

if [ ! -x "$PYTHON" ]; then
    echo "$APP_NAME: не найден Python: $PYTHON" >&2
    exit 1
fi

if [ ! -f "$PROGRAM" ]; then
    echo "$APP_NAME: не найден backend: $PROGRAM" >&2
    exit 1
fi

# Do not wait for Moonraker HTTP here. The wrapper already waited for the
# Moonraker process/chroot; the backend monitor is designed to recover from
# temporary Moonraker or Spoolman unavailability after it starts.
nohup "$PYTHON" "$PROGRAM" >>"$LOG_FILE" 2>&1 </dev/null &
NEW_PID=$!

echo "$NEW_PID" >"$PID_FILE"

sleep 1

if pid_is_plugin "$NEW_PID"; then
    echo "$APP_NAME запущен: PID $NEW_PID"
    exit 0
fi

echo "$APP_NAME не запустился." >&2
tail -n 50 "$LOG_FILE" 2>/dev/null || true
rm -f "$PID_FILE"

exit 1
