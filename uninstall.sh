#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"

# Z-Mod calls this file from DISABLE_PLUGIN. Disabling must remove the active
# runtime while keeping the Git checkout and update_manager registration so the
# plugin can be enabled again through the normal Z-Mod mechanism.
if [ ! -d "$TARGET_DIR" ]; then
    echo "$APP_NAME: runtime уже отсутствует; Git source checkout сохранён."
    exit 0
fi

[ -x "$TARGET_DIR/uninstall.sh" ] || {
    echo "$APP_NAME: runtime uninstall.sh отсутствует: $TARGET_DIR/uninstall.sh" >&2
    exit 1
}

"$TARGET_DIR/uninstall.sh" --yes

echo "$APP_NAME: отключён. Git checkout и update_manager сохранены для ENABLE_PLUGIN."
