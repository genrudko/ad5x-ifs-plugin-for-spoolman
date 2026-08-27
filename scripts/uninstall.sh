#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/usr/data/config/mod_data/ifs_spoolman"
ZMOD_ROOT="/usr/data/.mod/.zmod"

CONFIRMED=0
PURGE=0

for ARG in "$@"; do
    case "$ARG" in
        --yes)
            CONFIRMED=1
            ;;
        --purge)
            PURGE=1
            ;;
        --help|-h)
            cat <<'HELP'
Usage:
  ./uninstall.sh --yes
      Remove plugin and keep user data in a backup directory.

  ./uninstall.sh --yes --purge
      Remove plugin and permanently delete user data.
HELP
            exit 0
            ;;
        *)
            echo "Unknown argument: $ARG"
            exit 2
            ;;
    esac
done

if [ "$CONFIRMED" -ne 1 ]; then
    echo "Uninstall confirmation required."
    echo "Run: ./uninstall.sh --yes"
    exit 2
fi

if [ -x "$APP_DIR/power_on_hook.sh" ]; then
    "$APP_DIR/power_on_hook.sh" remove || {
        echo "$APP_NAME: не удалось безопасно удалить блок автозапуска." >&2
        exit 1
    }
fi

"$APP_DIR/stop.sh" || true

MOON_PID=""
ROOT=""

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

if [ -n "$MOON_PID" ] && [ -d "/proc/$MOON_PID/root" ]; then
    ROOT="/proc/$MOON_PID/root"
elif [ -d "$ZMOD_ROOT" ]; then
    ROOT="$ZMOD_ROOT"
fi

if [ -n "$ROOT" ]; then
    if chroot "$ROOT" /bin/sh -c \
        "[ -x '/opt/config/mod_data/ifs_spoolman/uninstall_fluidd_card.sh' ]"
    then
        if ! chroot "$ROOT" \
            /opt/config/mod_data/ifs_spoolman/uninstall_fluidd_card.sh
        then
            echo "$APP_NAME: WARNING: не удалось полностью очистить Fluidd-интеграцию." >&2
        fi
    fi
else
    echo "$APP_NAME: WARNING: корень Z-Mod не найден; Fluidd-интеграция не проверена." >&2
fi

if [ "$PURGE" -eq 0 ]; then
    STAMP="$(date +%Y%m%d_%H%M%S)"
    DATA_BACKUP="/usr/data/config/mod_data/ad5x_ifs_user_data_$STAMP"

    mkdir -p "$DATA_BACKUP"

    for FILE in \
        config.json \
        assignments.json \
        events.log \
        events.log.1 \
        events.log.2 \
        events.log.3 \
        ifs_spoolman.log \
        fluidd_card.log \
        boot.log
    do
        [ -f "$APP_DIR/$FILE" ] || continue
        cp "$APP_DIR/$FILE" "$DATA_BACKUP/$FILE"
    done

    echo "User data backup: $DATA_BACKUP"
fi

rm -rf "$APP_DIR"

echo "$APP_NAME удалён."
