#!/bin/sh
set -eu
TARGET_DIR="${AD5X_IFS_TARGET_DIR:-/usr/data/config/mod_data/ifs_spoolman}"
LEGACY_SOURCE="${AD5X_IFS_LEGACY_SOURCE:-/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman}"
PYTHON="${AD5X_IFS_PYTHON:-/root/moonraker-env/bin/python3}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python3 2>/dev/null || true)"
fi
[ -n "$PYTHON" ] || { echo "AD5X IFS: Python not found for assignment recovery" >&2; exit 1; }
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$PYTHON" "$SCRIPT_DIR/recover_assignments.py" "$TARGET_DIR" "$LEGACY_SOURCE"
