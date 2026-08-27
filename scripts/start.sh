#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
INNER_BOOT="/opt/config/mod_data/ifs_spoolman/boot_start.sh"
WAIT_SECONDS="${IFS_START_WAIT_SECONDS:-120}"

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

if ! chroot "$ROOT" /bin/sh -c \
    "[ -x '$INNER_BOOT' ]"
then
    echo "$APP_NAME: boot_start.sh не найден в chroot." >&2
    exit 1
fi

chroot "$ROOT" "$INNER_BOOT"
