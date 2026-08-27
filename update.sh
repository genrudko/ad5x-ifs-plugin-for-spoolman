#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DRY_RUN=0
BACKUP_KEEP=5

case "${1:-}" in
    "") ;;
    --dry-run|--check) DRY_RUN=1 ;;
    --help|-h)
        echo "Usage: ./update.sh [--dry-run]"
        exit 0
        ;;
    *)
        echo "Unknown argument: $1"
        exit 2
        ;;
esac

PLUGIN_FILES="ifs_spoolman.py ui_v0_2.html ifs-spoolman-card.js ifs-spoolman-layout.js ifs-spoolman-dashboard.js ifs-spoolman-visibility.js ifs-spoolman-selection.js"
SCRIPT_FILES="boot_start.sh start.sh stop.sh status.sh update.sh uninstall.sh install_fluidd_card.sh uninstall_fluidd_card.sh power_on_hook.sh"

for FILE in $PLUGIN_FILES; do
    [ -f "$REPO_DIR/plugin/$FILE" ] || {
        echo "Missing plugin/$FILE"
        exit 1
    }
done

for FILE in $SCRIPT_FILES; do
    [ -f "$REPO_DIR/scripts/$FILE" ] || {
        echo "Missing scripts/$FILE"
        exit 1
    }
done

for FILE in VERSION PACKAGE_MANIFEST.txt; do
    [ -f "$REPO_DIR/$FILE" ] || {
        echo "Missing $FILE"
        exit 1
    }
done

if [ "$DRY_RUN" -eq 1 ]; then
    echo "$APP_NAME update preflight: OK"
    echo "Source: $REPO_DIR"
    echo "Target: $TARGET_DIR"
    echo "Version: $(cat "$REPO_DIR/VERSION")"
    exit 0
fi

[ -d "$TARGET_DIR" ] || {
    echo "$APP_NAME is not installed."
    exit 1
}

prune_backups() {
    [ -d "$TARGET_DIR/backups" ] || return 0
    COUNT=0
    for DIR in $(ls -1dt "$TARGET_DIR"/backups/update_* 2>/dev/null || true); do
        COUNT=$((COUNT + 1))
        if [ "$COUNT" -gt "$BACKUP_KEEP" ]; then
            rm -rf "$DIR"
        fi
    done
}

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$TARGET_DIR/backups/update_$STAMP"
mkdir -p "$BACKUP_DIR"

for FILE in $PLUGIN_FILES $SCRIPT_FILES install.sh VERSION PACKAGE_MANIFEST.txt config.json assignments.json; do
    [ -f "$TARGET_DIR/$FILE" ] && cp "$TARGET_DIR/$FILE" "$BACKUP_DIR/$FILE"
done

rollback() {
    echo "$APP_NAME: rollback."
    "$TARGET_DIR/stop.sh" 2>/dev/null || true
    for FILE in "$BACKUP_DIR"/*; do
        [ -f "$FILE" ] && cp "$FILE" "$TARGET_DIR/${FILE##*/}"
    done
    chmod +x "$TARGET_DIR"/*.sh 2>/dev/null || true
    if [ -x "$TARGET_DIR/power_on_hook.sh" ]; then
        "$TARGET_DIR/power_on_hook.sh" install 2>/dev/null || true
    fi
    "$TARGET_DIR/start.sh" 2>/dev/null || true
    prune_backups
}

"$TARGET_DIR/stop.sh" || true
for FILE in $PLUGIN_FILES; do
    cp "$REPO_DIR/plugin/$FILE" "$TARGET_DIR/$FILE"
done
for FILE in $SCRIPT_FILES; do
    cp "$REPO_DIR/scripts/$FILE" "$TARGET_DIR/$FILE"
done
cp "$REPO_DIR/install.sh" "$TARGET_DIR/install.sh"
cp "$REPO_DIR/VERSION" "$TARGET_DIR/VERSION"
cp "$REPO_DIR/PACKAGE_MANIFEST.txt" "$TARGET_DIR/PACKAGE_MANIFEST.txt"
chmod +x "$TARGET_DIR"/*.sh
"$TARGET_DIR/power_on_hook.sh" install

if ! "$TARGET_DIR/start.sh"; then
    rollback
    exit 1
fi
sleep 3
if ! wget -qO- http://127.0.0.1:7913/api/health >/dev/null 2>&1; then
    rollback
    exit 1
fi

prune_backups

echo "$APP_NAME updated."
echo "Backup: $BACKUP_DIR"
echo "Retained update backups: $BACKUP_KEEP"
echo "Version: $(cat "$TARGET_DIR/VERSION")"
