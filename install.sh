#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
UPDATE_MANAGER_HOOK="$REPO_DIR/scripts/update_manager_hook.sh"
NO_START=0

case "${1:-}" in
    "") ;;
    --no-start) NO_START=1 ;;
    --help|-h)
        echo "Usage: ./install.sh [--no-start]"
        exit 0
        ;;
    *)
        echo "Unknown argument: $1"
        exit 2
        ;;
esac

PLUGIN_FILES="ifs_spoolman.py ui_v0_2.html ifs-spoolman-card.js ifs-spoolman-layout.js ifs-spoolman-dashboard.js ifs-spoolman-visibility.js ifs-spoolman-selection.js"
SCRIPT_FILES="boot_start.sh start.sh stop.sh status.sh update.sh uninstall.sh install_fluidd_card.sh uninstall_fluidd_card.sh install_fluidd_native.sh restore_fluidd_native.sh power_on_hook.sh"

for FILE in $PLUGIN_FILES; do
    [ -f "$REPO_DIR/plugin/$FILE" ] || {
        echo "$APP_NAME: missing plugin/$FILE"
        exit 1
    }
done
for FILE in $SCRIPT_FILES; do
    [ -f "$REPO_DIR/scripts/$FILE" ] || {
        echo "$APP_NAME: missing scripts/$FILE"
        exit 1
    }
done
for FILE in VERSION PACKAGE_MANIFEST.txt; do
    [ -f "$REPO_DIR/$FILE" ] || {
        echo "$APP_NAME: missing $FILE"
        exit 1
    }
done
[ -x "$UPDATE_MANAGER_HOOK" ] || {
    echo "$APP_NAME: missing scripts/update_manager_hook.sh"
    exit 1
}

# A normal Z-Mod ENABLE_PLUGIN call reaches this script after the source repo
# has already been registered. Direct Git installs also become managed, but an
# existing bootstrap-selected dev/stable block is deliberately preserved.
if ! "$UPDATE_MANAGER_HOOK" present >/dev/null 2>&1; then
    "$UPDATE_MANAGER_HOOK" install
fi

# Migration from the historical raw-file installation must go through the
# transactional updater so config.json, assignments.json, power_on.sh and the
# currently working runtime can be rolled back on failure.
if [ -d "$TARGET_DIR" ] && [ -f "$TARGET_DIR/ifs_spoolman.py" ]; then
    echo "$APP_NAME: existing runtime detected; using safe update path."
    exec "$REPO_DIR/update.sh"
fi

mkdir -p "$TARGET_DIR"
for FILE in $PLUGIN_FILES; do cp "$REPO_DIR/plugin/$FILE" "$TARGET_DIR/$FILE"; done
for FILE in $SCRIPT_FILES; do cp "$REPO_DIR/scripts/$FILE" "$TARGET_DIR/$FILE"; done
cp "$REPO_DIR/install.sh" "$TARGET_DIR/install.sh"
cp "$REPO_DIR/VERSION" "$TARGET_DIR/VERSION"
cp "$REPO_DIR/PACKAGE_MANIFEST.txt" "$TARGET_DIR/PACKAGE_MANIFEST.txt"

for FILE in config assignments; do
    if [ ! -f "$TARGET_DIR/$FILE.json" ] && [ -f "$REPO_DIR/examples/$FILE.example.json" ]; then
        cp "$REPO_DIR/examples/$FILE.example.json" "$TARGET_DIR/$FILE.json"
    fi
done

chmod +x "$TARGET_DIR"/*.sh
"$TARGET_DIR/power_on_hook.sh" install

if [ "$NO_START" -eq 0 ]; then
    "$TARGET_DIR/start.sh"
fi

echo "$APP_NAME installed."
echo "Path: $TARGET_DIR"
echo "Source: $REPO_DIR"
echo "Updates: Z-Mod/Moonraker git_repo"
echo "Web UI: http://PRINTER_IP:7913/"
