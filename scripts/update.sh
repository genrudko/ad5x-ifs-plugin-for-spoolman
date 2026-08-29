#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="${AD5X_IFS_TARGET_DIR:-/usr/data/config/mod_data/ifs_spoolman}"
BACKUP_KEEP=5

SOURCE_DIR="$(
    CDPATH= cd -- "$(dirname -- "$0")"
    pwd
)"

DRY_RUN=0
RECOVER_ONLY=0
LEGACY_SOURCE="${AD5X_IFS_LEGACY_SOURCE:-/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman}"

case "${1:-}" in
    "") ;;
    --dry-run|--check) DRY_RUN=1 ;;
    --recover-only) RECOVER_ONLY=1 ;;
    --help|-h)
        echo "Usage: ./update.sh [--dry-run|--recover-only]"
        exit 0
        ;;
    *)
        echo "Unknown argument: $1"
        exit 2
        ;;
esac

recover_assignments() {
    PYTHON="${AD5X_IFS_PYTHON:-/root/moonraker-env/bin/python3}"
    if [ ! -x "$PYTHON" ]; then
        PYTHON="$(command -v python3 2>/dev/null || true)"
    fi
    [ -n "$PYTHON" ] || {
        echo "$APP_NAME: Python not found for assignment recovery" >&2
        return 1
    }

    "$PYTHON" - "$TARGET_DIR" "$LEGACY_SOURCE" <<'PY'
import json
import os
import sys
from pathlib import Path

target = Path(sys.argv[1])
legacy = Path(sys.argv[2])
out = target / "assignments.json"

def load(path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    result, seen, count = {}, set(), 0
    for slot in range(1, 5):
        value = raw.get(str(slot))
        if value in (None, "", 0, "0"):
            result[str(slot)] = None
            continue
        if isinstance(value, bool):
            return None
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        if value <= 0 or value in seen:
            return None
        seen.add(value)
        result[str(slot)] = value
        count += 1
    return result, count

current = load(out) if out.exists() else None
if current and current[1] > 0:
    print(f"IFS assignments preserved: {current[1]}/4")
    raise SystemExit(0)

candidates = []
def add(path):
    if not path.exists() or path.resolve() == out.resolve():
        return
    try:
        modified = path.stat().st_mtime
    except OSError:
        modified = 0
    candidates.append((modified, path))

add(legacy / "assignments.json")
for path in legacy.parent.glob(legacy.name + ".pre-git-*/assignments.json"):
    add(path)
for path in target.parent.glob(target.name + ".pre-git-*/assignments.json"):
    add(path)
for path in (target / "backups").glob("update_*/assignments.json"):
    add(path)
plugins = target.parent / "plugins"
if plugins.is_dir():
    for path in plugins.glob("*ifs*spoolman*.pre-git-*/assignments.json"):
        add(path)

for _, path in sorted(candidates, key=lambda item: item[0], reverse=True):
    parsed = load(path)
    if not parsed or parsed[1] == 0:
        continue
    data, count = parsed
    target.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".recover.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(f"IFS assignments recovered: {count}/4 from {path}")
    raise SystemExit(0)

if current is None and out.exists():
    print("WARNING: current assignments.json is invalid; no valid legacy mapping found", file=sys.stderr)
else:
    print("IFS assignments recovery: no previous non-empty mapping found")
PY
}

if [ "$RECOVER_ONLY" -eq 1 ]; then
    recover_assignments
    exit 0
fi

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

recover_assignments

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$TARGET_DIR/backups/update_$STAMP"
mkdir -p "$BACKUP_DIR"

for FILE in $REQUIRED_FILES config.json assignments.json; do
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
    if [ -x "$TARGET_DIR/power_on_hook.sh" ]; then
        "$TARGET_DIR/power_on_hook.sh" install 2>/dev/null || true
    fi
    "$TARGET_DIR/start.sh" 2>/dev/null || true
    prune_backups
}

"$TARGET_DIR/stop.sh" || true

if [ "$SOURCE_DIR" != "$TARGET_DIR" ]; then
    for FILE in $REQUIRED_FILES; do
        cp "$SOURCE_DIR/$FILE" "$TARGET_DIR/$FILE"
    done
fi

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

echo "$APP_NAME обновлён."
echo "Backup: $BACKUP_DIR"
echo "Retained update backups: $BACKUP_KEEP"
echo "Version: $(cat "$TARGET_DIR/VERSION")"
