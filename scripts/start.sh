#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
INNER_BOOT="/opt/config/mod_data/ifs_spoolman/boot_start.sh"
WAIT_SECONDS="${IFS_START_WAIT_SECONDS:-120}"
NATIVE_PATCH_REVISION="10"
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
current_fluidd_version() {
    FLUIDD_ROOT="$ROOT/root/fluidd"
    VERSION=""

    if [ -f "$FLUIDD_ROOT/release_info.json" ]; then
        PROJECT_NAME="$(sed -n 's/.*"project_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$FLUIDD_ROOT/release_info.json" | head -n 1)"
        PROJECT_OWNER="$(sed -n 's/.*"project_owner"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$FLUIDD_ROOT/release_info.json" | head -n 1)"
        VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$FLUIDD_ROOT/release_info.json" | head -n 1)"
        case "$VERSION" in
            v[0-9]*.[0-9]*.[0-9]*)
                if [ "$PROJECT_NAME" = "fluidd" ] && [ "$PROJECT_OWNER" = "ghzserg" ]; then
                    printf '%s\n' "$VERSION"
                    return 0
                fi
                ;;
        esac
    fi

    VERSION="$(cat "$FLUIDD_ROOT/.version" 2>/dev/null || true)"
    case "$VERSION" in
        v[0-9]*.[0-9]*.[0-9]*)
            printf '%s\n' "$VERSION"
            return 0
            ;;
    esac

    return 1
}

CURRENT_FLUIDD_UPSTREAM="$(current_fluidd_version 2>/dev/null || true)"

if fluidd_enabled; then
    INSTALLED_NATIVE_PATCH=""
    INSTALLED_NATIVE_UPSTREAM=""
    if [ -f "$NATIVE_MARKER" ]; then
        INSTALLED_NATIVE_PATCH="$(sed -n 's/.*"patch_revision"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$NATIVE_MARKER" | head -n 1)"
        INSTALLED_NATIVE_UPSTREAM="$(sed -n 's/.*"upstream_tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$NATIVE_MARKER" | head -n 1)"
    fi

    if { [ "$INSTALLED_NATIVE_PATCH" != "$NATIVE_PATCH_REVISION" ] || [ "$INSTALLED_NATIVE_UPSTREAM" != "$CURRENT_FLUIDD_UPSTREAM" ]; } && [ -x "$APP_DIR/install_fluidd_native.sh" ]; then
        echo "$APP_NAME: native Fluidd state patch ${INSTALLED_NATIVE_PATCH:-missing} -> $NATIVE_PATCH_REVISION, upstream ${INSTALLED_NATIVE_UPSTREAM:-missing} -> ${CURRENT_FLUIDD_UPSTREAM:-missing}; updating." >>"$NATIVE_LOG" 2>&1 || true
        AD5X_IFS_FLUIDD_PATCH_REVISION="$NATIVE_PATCH_REVISION" \
            "$APP_DIR/install_fluidd_native.sh" >>"$NATIVE_LOG" 2>&1 || {
                echo "$APP_NAME: native Fluidd repair unavailable; legacy automatic fallback is disabled." \
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
