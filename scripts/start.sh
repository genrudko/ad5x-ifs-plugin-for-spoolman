#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
INNER_BOOT="/opt/config/mod_data/ifs_spoolman/boot_start.sh"
WAIT_SECONDS="${IFS_START_WAIT_SECONDS:-120}"
NATIVE_PATCH_REVISION="9"
NATIVE_LOG="$APP_DIR/fluidd_native.log"

find_moonraker_pid() {
    for P in /proc/[0-9]*; do
        [ -r "$P/cmdline" ] || continue

        CMD="$(tr '\0' ' ' <"$P/cmdline" 2>/dev/null || true)"

        case "$CMD" in
            *moonraker.py*)
                if [ -d "$P/root" ]; then
                    echo "${P##*/}"
                    return 0
                fi
                ;;
        esac
    done

    return 1
}

fluidd_enabled() {
    [ -f "$APP_DIR/config.json" ] || return 0
    if grep -Eq '"fluidd_integration"[[:space:]]*:[[:space:]]*false([[:space:],}]|$)' "$APP_DIR/config.json"; then
        return 1
    fi
    return 0
}

MOON_PID=""
i=0

while [ "$i" -lt "$WAIT_SECONDS" ]; do
    MOON_PID="$(find_moonraker_pid 2>/dev/null || true)"

    if [ -n "$MOON_PID" ]; then
        break
    fi

    i=$((i + 1))
    sleep 1
done

if [ -z "$MOON_PID" ]; then
    echo "$APP_NAME: Moonraker не появился за ${WAIT_SECONDS} с." >&2
    exit 1
fi

ROOT="/proc/$MOON_PID/root"
NATIVE_MARKER="$ROOT/root/fluidd/ad5x_ifs_native.json"

if fluidd_enabled; then
    INSTALLED_NATIVE_PATCH=""
    if [ -f "$NATIVE_MARKER" ]; then
        INSTALLED_NATIVE_PATCH="$(sed -n 's/.*"patch_revision"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$NATIVE_MARKER" | head -n 1)"
    fi

    if [ "$INSTALLED_NATIVE_PATCH" != "$NATIVE_PATCH_REVISION" ] && [ -x "$APP_DIR/install_fluidd_native.sh" ]; then
        echo "$APP_NAME: native Fluidd patch ${INSTALLED_NATIVE_PATCH:-missing} -> $NATIVE_PATCH_REVISION; updating." >>"$NATIVE_LOG" 2>&1 || true
        AD5X_IFS_FLUIDD_PATCH_REVISION="$NATIVE_PATCH_REVISION" \
            "$APP_DIR/install_fluidd_native.sh" >>"$NATIVE_LOG" 2>&1 || {
                echo "$APP_NAME: native Fluidd repair unavailable; legacy integration will be used." \
                    >>"$NATIVE_LOG" 2>&1 || true
            }
    fi
else
    if [ -f "$NATIVE_MARKER" ] && [ -x "$APP_DIR/restore_fluidd_native.sh" ]; then
        "$APP_DIR/restore_fluidd_native.sh" >>"$NATIVE_LOG" 2>&1 || {
            echo "$APP_NAME: WARNING: native Fluidd integration could not be removed automatically." \
                >>"$NATIVE_LOG" 2>&1 || true
        }
    fi
fi

if ! chroot "$ROOT" /bin/sh -c \
    "[ -x '$INNER_BOOT' ]"
then
    echo "$APP_NAME: boot_start.sh не найден в chroot." >&2
    exit 1
fi

chroot "$ROOT" "$INNER_BOOT"
