#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
POWER_ON="/usr/data/config/mod_data/power_on.sh"
USER_MOONRAKER="/usr/data/config/mod_data/user.moonraker.conf"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
UPDATE_MANAGER_HOOK="$REPO_DIR/scripts/update_manager_hook.sh"
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
SCRIPT_FILES="boot_start.sh start.sh stop.sh status.sh update.sh uninstall.sh install_fluidd_card.sh uninstall_fluidd_card.sh install_fluidd_native.sh restore_fluidd_native.sh power_on_hook.sh"
TRACKED_FILES="$PLUGIN_FILES $SCRIPT_FILES install.sh VERSION PACKAGE_MANIFEST.txt config.json assignments.json"

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
[ -x "$UPDATE_MANAGER_HOOK" ] || {
    echo "Missing scripts/update_manager_hook.sh"
    exit 1
}

if [ "$DRY_RUN" -eq 1 ]; then
    echo "$APP_NAME update preflight: OK"
    echo "Source: $REPO_DIR"
    echo "Target: $TARGET_DIR"
    echo "Version: $(cat "$REPO_DIR/VERSION")"
    if [ -d "$TARGET_DIR" ]; then
        echo "Runtime: enabled"
    else
        echo "Runtime: disabled/not installed; source-only update will be accepted"
    fi
    exit 0
fi

# Moonraker also updates disabled plugin repositories. Keep DISABLE_PLUGIN
# sticky: update the Git source successfully, but do not recreate the runtime.
if [ ! -d "$TARGET_DIR" ]; then
    if ! "$UPDATE_MANAGER_HOOK" present >/dev/null 2>&1; then
        "$UPDATE_MANAGER_HOOK" install
    fi
    echo "$APP_NAME source updated; runtime is disabled, apply skipped."
    exit 0
fi

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

snapshot_path() {
    SNAP_PATH="$1"
    SNAP_KEY="$2"

    rm -f \
        "$BACKUP_DIR/$SNAP_KEY" \
        "$BACKUP_DIR/.absent-$SNAP_KEY" \
        "$BACKUP_DIR/.symlink-$SNAP_KEY"

    if [ -L "$SNAP_PATH" ]; then
        readlink "$SNAP_PATH" >"$BACKUP_DIR/.symlink-$SNAP_KEY"
    elif [ -e "$SNAP_PATH" ]; then
        cp -p "$SNAP_PATH" "$BACKUP_DIR/$SNAP_KEY"
    else
        : >"$BACKUP_DIR/.absent-$SNAP_KEY"
    fi
}

restore_path() {
    RESTORE_PATH="$1"
    RESTORE_KEY="$2"

    rm -f "$RESTORE_PATH"

    if [ -f "$BACKUP_DIR/.absent-$RESTORE_KEY" ]; then
        return 0
    fi

    mkdir -p "${RESTORE_PATH%/*}"

    if [ -f "$BACKUP_DIR/.symlink-$RESTORE_KEY" ]; then
        ln -s "$(cat "$BACKUP_DIR/.symlink-$RESTORE_KEY")" "$RESTORE_PATH"
    elif [ -e "$BACKUP_DIR/$RESTORE_KEY" ]; then
        cp -p "$BACKUP_DIR/$RESTORE_KEY" "$RESTORE_PATH"
    fi
}

for FILE in $TRACKED_FILES; do
    snapshot_path "$TARGET_DIR/$FILE" "$FILE"
done
snapshot_path "$POWER_ON" "external-power_on.sh"
snapshot_path "$USER_MOONRAKER" "external-user.moonraker.conf"

rollback() {
    echo "$APP_NAME: rollback."
    "$TARGET_DIR/stop.sh" 2>/dev/null || true

    for FILE in $TRACKED_FILES; do
        restore_path "$TARGET_DIR/$FILE" "$FILE"
    done
    restore_path "$POWER_ON" "external-power_on.sh"
    restore_path "$USER_MOONRAKER" "external-user.moonraker.conf"

    if [ -x "$TARGET_DIR/start.sh" ]; then
        "$TARGET_DIR/start.sh" 2>/dev/null || true
    fi
    prune_backups
}

ROLLBACK_ARMED=1

on_exit() {
    RC=$?
    trap - EXIT HUP INT TERM
    if [ "$ROLLBACK_ARMED" -eq 1 ] && [ "$RC" -ne 0 ]; then
        rollback || true
    fi
    exit "$RC"
}

on_signal() {
    trap - EXIT HUP INT TERM
    if [ "$ROLLBACK_ARMED" -eq 1 ]; then
        rollback || true
    fi
    exit 1
}

trap on_exit EXIT
trap on_signal HUP INT TERM

if ! "$UPDATE_MANAGER_HOOK" present >/dev/null 2>&1; then
    "$UPDATE_MANAGER_HOOK" install
fi

"$TARGET_DIR/stop.sh" || true
for FILE in $PLUGIN_FILES; do cp "$REPO_DIR/plugin/$FILE" "$TARGET_DIR/$FILE"; done
for FILE in $SCRIPT_FILES; do cp "$REPO_DIR/scripts/$FILE" "$TARGET_DIR/$FILE"; done
cp "$REPO_DIR/install.sh" "$TARGET_DIR/install.sh"
cp "$REPO_DIR/VERSION" "$TARGET_DIR/VERSION"
cp "$REPO_DIR/PACKAGE_MANIFEST.txt" "$TARGET_DIR/PACKAGE_MANIFEST.txt"
chmod +x "$TARGET_DIR"/*.sh
"$TARGET_DIR/power_on_hook.sh" install

if ! "$TARGET_DIR/start.sh"; then
    exit 1
fi
sleep 3
if ! wget -qO- http://127.0.0.1:7913/api/health >/dev/null 2>&1; then
    exit 1
fi

ROLLBACK_ARMED=0
prune_backups

echo "$APP_NAME updated."
echo "Backup: $BACKUP_DIR"
echo "Retained update backups: $BACKUP_KEEP"
echo "Version: $(cat "$TARGET_DIR/VERSION")"
echo "Source: $REPO_DIR"
echo "Delivery: Z-Mod/Moonraker git_repo"
