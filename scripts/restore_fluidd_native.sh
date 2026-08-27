#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"

find_moonraker_pid() {
    for P in /proc/[0-9]*; do
        [ -r "$P/cmdline" ] || continue
        CMD="$(tr '\0' ' ' <"$P/cmdline" 2>/dev/null || true)"
        case "$CMD" in
            *moonraker.py*)
                [ -d "$P/root" ] || continue
                echo "${P##*/}"
                return 0
                ;;
        esac
    done
    return 1
}

[ "$(id -u)" = "0" ] || {
    echo "$APP_NAME: run this script over SSH as root." >&2
    exit 1
}

MOON_PID="$(find_moonraker_pid 2>/dev/null || true)"
[ -n "$MOON_PID" ] || {
    echo "$APP_NAME: Moonraker process/chroot not found." >&2
    exit 1
}

ROOT="/proc/$MOON_PID/root"

chroot "$ROOT" /bin/sh -s <<'INNER'
set -eu

FLUIDD_DIR="/root/fluidd"
PREVIOUS_DIR="/root/fluidd.ifs-previous"
FAILED_DIR="/root/fluidd.ifs-native-removed.$$"

[ -d "$FLUIDD_DIR" ] || {
    echo "AD5X IFS native Fluidd: current Fluidd directory is missing." >&2
    exit 1
}

[ -d "$PREVIOUS_DIR" ] || {
    echo "AD5X IFS native Fluidd: rollback snapshot not found: $PREVIOUS_DIR" >&2
    exit 1
}

CURRENT_VERSION="$(cat "$FLUIDD_DIR/.version" 2>/dev/null || true)"
PREVIOUS_VERSION="$(cat "$PREVIOUS_DIR/.version" 2>/dev/null || true)"

[ -n "$CURRENT_VERSION" ] || {
    echo "AD5X IFS native Fluidd: current .version is missing." >&2
    exit 1
}
[ "$PREVIOUS_VERSION" = "$CURRENT_VERSION" ] || {
    echo "AD5X IFS native Fluidd: refusing cross-version rollback ($CURRENT_VERSION -> $PREVIOUS_VERSION)." >&2
    exit 1
}

rm -rf "$FAILED_DIR"
mv "$FLUIDD_DIR" "$FAILED_DIR"

if ! mv "$PREVIOUS_DIR" "$FLUIDD_DIR"; then
    mv "$FAILED_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    echo "AD5X IFS native Fluidd: rollback failed; native Fluidd restored." >&2
    exit 1
fi

if [ ! -f "$FLUIDD_DIR/index.html" ]; then
    rm -rf "$PREVIOUS_DIR" 2>/dev/null || true
    mv "$FLUIDD_DIR" "$PREVIOUS_DIR" 2>/dev/null || true
    mv "$FAILED_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    echo "AD5X IFS native Fluidd: rollback snapshot validation failed; native Fluidd restored." >&2
    exit 1
fi

rm -rf "$FAILED_DIR"
echo "AD5X IFS native Fluidd removed."
echo "Restored previous Fluidd: $CURRENT_VERSION"
INNER
