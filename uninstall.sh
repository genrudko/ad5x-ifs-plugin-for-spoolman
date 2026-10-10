#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
REPO_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
SOURCE_UNINSTALL="$REPO_DIR/scripts/uninstall.sh"

# Z-Mod runs this entrypoint from the freshly pulled Git checkout.  The
# installed runtime may be stale if an update was source-only or if the last
# DISABLE_PLUGIN failed.  Never delegate to its old uninstall.sh: use the
# matching freshly pulled source scripts instead.
if [ ! -d "$TARGET_DIR" ]; then
    echo "$APP_NAME: runtime уже отсутствует; Git source checkout сохранён."
    exit 0
fi

[ -f "$SOURCE_UNINSTALL" ] || {
    echo "$APP_NAME: source uninstall.sh отсутствует: $SOURCE_UNINSTALL" >&2
    exit 1
}

if ! sh "$SOURCE_UNINSTALL" --yes; then
    echo "$APP_NAME: deinstallation failed; runtime kept for recovery." >&2
    # Z-Mod removes the include from plugins.cfg before invoking uninstall.sh,
    # even if uninstall fails. Restore the existing plugin include to avoid an
    # unintended implicit disable on the following FIRMWARE_RESTART.
    CFG="/usr/data/config/mod_data/plugins.cfg"
    SOURCE_CFG="$REPO_DIR/ad5x_ifs_spoolman.cfg"
    INCLUDE="[include plugins/ad5x_ifs_spoolman/ad5x_ifs_spoolman.cfg]"
    if [ -f "$SOURCE_CFG" ] && [ -f "$CFG" ]; then
        if ! grep -Fqx "$INCLUDE" "$CFG"; then
            printf '\n%s\n' "$INCLUDE" >> "$CFG"
            echo "$APP_NAME: restored plugin include after failed uninstall."
        fi
    fi
    exit 1
fi

echo "$APP_NAME: отключён. Git checkout и update_manager сохранены для ENABLE_PLUGIN."
