#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"

SOURCE_DIR="$(
    CDPATH= cd -- "$(dirname -- "$0")"
    pwd
)"

NO_START=0

case "${1:-}" in
    "")
        ;;
    --no-start)
        NO_START=1
        ;;
    --help|-h)
        echo "Usage: ./install.sh [--no-start]"
        exit 0
        ;;
    *)
        echo "Unknown argument: $1"
        exit 2
        ;;
esac

REQUIRED_FILES="
ifs_spoolman.py
ui_v0_2.html
ifs-spoolman-card.js
ifs-spoolman-layout.js
ifs-spoolman-dashboard.js
ifs-spoolman-visibility.js
ifs-spoolman-selection.js
install_fluidd_card.sh
uninstall_fluidd_card.sh
install_fluidd_native.sh
restore_fluidd_native.sh
power_on_hook.sh
boot_start.sh
start.sh
stop.sh
status.sh
install.sh
update.sh
uninstall.sh
VERSION
PACKAGE_MANIFEST.txt
"

for FILE in $REQUIRED_FILES; do
    if [ ! -f "$SOURCE_DIR/$FILE" ]; then
        echo "$APP_NAME: отсутствует исходный файл: $FILE"
        exit 1
    fi
done

mkdir -p "$TARGET_DIR"

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    for FILE in $REQUIRED_FILES; do
        cp "$SOURCE_DIR/$FILE" "$TARGET_DIR/$FILE"
    done

    for FILE in config.json assignments.json; do
        if [ ! -f "$TARGET_DIR/$FILE" ] &&
            [ -f "$SOURCE_DIR/$FILE" ]
        then
            cp "$SOURCE_DIR/$FILE" "$TARGET_DIR/$FILE"
        fi
    done
fi

sh "$TARGET_DIR/update.sh" --recover-only

chmod +x "$TARGET_DIR"/*.sh
"$TARGET_DIR/power_on_hook.sh" install

if [ "$NO_START" -eq 0 ]; then
    "$TARGET_DIR/start.sh"
fi

echo "$APP_NAME установлен."
echo "Путь: $TARGET_DIR"
echo "Web UI: http://PRINTER_IP:7913/"
