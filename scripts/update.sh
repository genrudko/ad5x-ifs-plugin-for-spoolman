#!/bin/sh
set -eu

APP_NAME="AD5X IFS Manager"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
SOURCE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DRY_RUN=0

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

REQUIRED_FILES="
ifs_spoolman.py
ifs_spoolman_runtime.py
ui_v0_2.html
ifs-spoolman-card.js
ifs-spoolman-layout.js
ifs-spoolman-dashboard.js
ifs-spoolman-visibility.js
ifs-spoolman-selection.js
install_fluidd_card.sh
uninstall_fluidd_card.sh
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

if [ "$DRY_RUN" -eq 1 ]; then
    echo "$APP_NAME update preflight: OK"
    echo "Source: $SOURCE_DIR"
    echo "Target: $TARGET_DIR"
    echo "Version: $(cat "$SOURCE_DIR/VERSION")"
    exit 0
fi

if [ ! -d "$TARGET_DIR" ]; then
    echo "$APP_NAME не установлен."
    echo "Используй install.sh."
    exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$TARGET_DIR/backups/update_$STAMP"
mkdir -p "$BACKUP_DIR"

for FILE in $REQUIRED_FILES config.json assignments.json inventory.json; do
    [ -f "$TARGET_DIR/$FILE" ] || continue
    cp "$TARGET_DIR/$FILE" "$BACKUP_DIR/$FILE"
done

rollback() {
    echo "$APP_NAME: выполняется rollback."
    "$TARGET_DIR/stop.sh" 2>/dev/null || true
    for FILE in "$BACKUP_DIR"/*; do
        [ -f "$FILE" ] || continue
        cp "$FILE" "$TARGET_DIR/${FILE##*/}"
    done
    chmod +x "$TARGET_DIR"/*.sh 2>/dev/null || true
    "$TARGET_DIR/start.sh" 2>/dev/null || true
}

"$TARGET_DIR/stop.sh" || true

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    for FILE in $REQUIRED_FILES; do
        cp "$SOURCE_DIR/$FILE" "$TARGET_DIR/$FILE"
    done
fi

chmod +x "$TARGET_DIR"/*.sh

if ! "$TARGET_DIR/start.sh"; then
    rollback
    exit 1
fi

sleep 3

if ! wget -qO- http://127.0.0.1:7913/api/health >/dev/null 2>&1; then
    rollback
    exit 1
fi

echo "$APP_NAME обновлён."
echo "Backup: $BACKUP_DIR"
echo "Version: $(cat "$TARGET_DIR/VERSION")"
