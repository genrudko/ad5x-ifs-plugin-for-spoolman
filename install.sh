#!/bin/sh
set -eu

APP_NAME="AD5X IFS Manager"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
NO_START=0

case "${1:-}" in
    "") ;;
    --no-start) NO_START=1 ;;
    --help|-h) echo "Usage: ./install.sh [--no-start]"; exit 0 ;;
    *) echo "Unknown argument: $1"; exit 2 ;;
esac

PLUGIN_FILES="ifs_spoolman.py ifs_spoolman_runtime.py ifs_spoolman_writer.py ifs_spoolman_ui.py zmod-filaments.html ui_v0_2.html ifs-spoolman-card.js ifs-spoolman-layout.js ifs-spoolman-dashboard.js ifs-spoolman-visibility.js ifs-spoolman-selection.js"
SCRIPT_FILES="boot_start.sh start.sh stop.sh status.sh update.sh uninstall.sh install_fluidd_card.sh uninstall_fluidd_card.sh"

for FILE in $PLUGIN_FILES; do
    [ -f "$REPO_DIR/plugin/$FILE" ] || { echo "$APP_NAME: missing plugin/$FILE"; exit 1; }
done
for FILE in $SCRIPT_FILES; do
    [ -f "$REPO_DIR/scripts/$FILE" ] || { echo "$APP_NAME: missing scripts/$FILE"; exit 1; }
done
for FILE in VERSION PACKAGE_MANIFEST.txt; do
    [ -f "$REPO_DIR/$FILE" ] || { echo "$APP_NAME: missing $FILE"; exit 1; }
done

mkdir -p "$TARGET_DIR"
for FILE in $PLUGIN_FILES; do cp "$REPO_DIR/plugin/$FILE" "$TARGET_DIR/$FILE"; done
for FILE in $SCRIPT_FILES; do cp "$REPO_DIR/scripts/$FILE" "$TARGET_DIR/$FILE"; done
cp "$REPO_DIR/install.sh" "$TARGET_DIR/install.sh"
cp "$REPO_DIR/VERSION" "$TARGET_DIR/VERSION"
cp "$REPO_DIR/PACKAGE_MANIFEST.txt" "$TARGET_DIR/PACKAGE_MANIFEST.txt"

for FILE in config assignments inventory; do
    if [ ! -f "$TARGET_DIR/$FILE.json" ] && [ -f "$REPO_DIR/examples/$FILE.example.json" ]; then
        cp "$REPO_DIR/examples/$FILE.example.json" "$TARGET_DIR/$FILE.json"
    fi
done

chmod +x "$TARGET_DIR"/*.sh
[ "$NO_START" -eq 1 ] || "$TARGET_DIR/start.sh"

echo "$APP_NAME installed."
echo "Path: $TARGET_DIR"
echo "Manager: http://PRINTER_IP:7913/manager"
