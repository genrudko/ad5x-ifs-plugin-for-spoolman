#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
INNER_BOOT="/opt/config/mod_data/ifs_spoolman/boot_start.sh"
MOON_PID=""

for P in /proc/[0-9]*; do
    [ -r "$P/cmdline" ] || continue

    CMD="$(tr '\0' ' ' <"$P/cmdline" 2>/dev/null || true)"

    case "$CMD" in
        *moonraker.py*)
            MOON_PID="${P##*/}"
            break
            ;;
    esac
done

if [ -z "$MOON_PID" ]; then
    echo "$APP_NAME: процесс Moonraker не найден."
    exit 1
fi

if [ ! -d "/proc/$MOON_PID/root" ]; then
    echo "$APP_NAME: корень chroot Moonraker недоступен."
    exit 1
fi

ROOT="/proc/$MOON_PID/root"

if ! chroot "$ROOT" /bin/sh -c \
    "[ -x '$INNER_BOOT' ]"
then
    echo "$APP_NAME: boot_start.sh не найден в chroot."
    exit 1
fi

chroot "$ROOT" "$INNER_BOOT"
