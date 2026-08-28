#!/bin/sh
set -eu

REPO_OWNER="genrudko"
REPO_NAME="ad5x-ifs-plugin-for-spoolman"
PLUGIN_NAME="ad5x_ifs_spoolman"
ORIGIN="https://github.com/$REPO_OWNER/$REPO_NAME.git"
REF="${AD5X_IFS_REF:-release/standalone-0.6.x}"
RAW_BASE="https://raw.githubusercontent.com/$REPO_OWNER/$REPO_NAME/$REF"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
SOURCE_DIR="/usr/data/config/mod_data/plugins/$PLUGIN_NAME"
ZMOD_ROOT="/usr/data/.mod/.zmod"
MOONRAKER_URL="http://127.0.0.1:7125"
NATIVE_PATCH_REVISION="4"
HOOK_TMP="/tmp/ad5x-ifs-update-manager-hook.sh"

# Z-Mod's stable plugin channel hard-resets a plugin checkout to the globally
# latest Git tag. This repository also carries non-version compatibility tags,
# so the supported release branch deliberately uses Moonraker's dev tracking
# mode. Release stability is controlled by REF=release/standalone-0.6.x.
UPDATE_CHANNEL="${AD5X_IFS_UPDATE_CHANNEL:-dev}"

fail() {
    echo "ОШИБКА: $*" >&2
    exit 1
}

cleanup() {
    rm -f "$HOOK_TMP"
}
trap cleanup EXIT HUP INT TERM

valid_ref() {
    case "$1" in
        ""|*[!A-Za-z0-9._/-]*) return 1 ;;
        *) return 0 ;;
    esac
}

find_plugins_script() {
    for FILE in \
        /usr/data/zmod/zmod/.shell/plugins.sh \
        /usr/data/config/mod/.shell/plugins.sh \
        /opt/config/mod/.shell/plugins.sh
    do
        [ -x "$FILE" ] || continue
        echo "$FILE"
        return 0
    done
    return 1
}

fluidd_enabled() {
    [ -f "$TARGET_DIR/config.json" ] || return 0
    if grep -Eq '"fluidd_integration"[[:space:]]*:[[:space:]]*false([[:space:],}]|$)' "$TARGET_DIR/config.json"; then
        return 1
    fi
    return 0
}

prepare_source_checkout() {
    # Pin the initial checkout to the requested branch before handing control to
    # Z-Mod plugins.sh. This avoids its generic `git clone` starting from the
    # repository default branch when our supported line is a maintenance branch.
    [ -d "$ZMOD_ROOT" ] || fail "Z-Mod chroot не найден: $ZMOD_ROOT"

    if [ -e "$SOURCE_DIR" ] && [ ! -d "$SOURCE_DIR/.git" ]; then
        STAMP="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo $$)"
        BACKUP="$SOURCE_DIR.pre-git-$STAMP"
        mv "$SOURCE_DIR" "$BACKUP"
        echo "Старый non-git source сохранён: $BACKUP"
    fi

    unset LD_LIBRARY_PATH LD_PRELOAD || true

    if [ ! -d "$SOURCE_DIR/.git" ]; then
        echo "Git checkout: $REF"
        chroot "$ZMOD_ROOT" /bin/bash -c \
            "git clone --branch '$REF' --single-branch '$ORIGIN' '/opt/config/mod_data/plugins/$PLUGIN_NAME'"
    else
        echo "Git checkout уже существует: синхронизирую $REF"
        chroot "$ZMOD_ROOT" /bin/bash -c \
            "cd '/opt/config/mod_data/plugins/$PLUGIN_NAME' && git fetch origin '$REF' && git checkout '$REF' && git pull --ff-only origin '$REF'"
    fi
}

echo "=== AD5X IFS Spoolman — Z-Mod Git bootstrap ==="
echo "Source ref: $REF"
echo "Update channel: $UPDATE_CHANNEL"

[ "$(id -u)" = "0" ] || fail "скрипт нужно запускать по SSH от root"
valid_ref "$REF" || fail "недопустимый git ref: $REF"
case "$UPDATE_CHANNEL" in stable|dev) ;; *) fail "channel должен быть stable или dev" ;; esac
command -v wget >/dev/null 2>&1 || fail "в системе не найден wget"

if ! wget -qO- "$MOONRAKER_URL/server/info" >/dev/null 2>&1; then
    fail "Moonraker недоступен по $MOONRAKER_URL. Проверьте установку и запуск Z-Mod"
fi

SPOOLMAN_STATUS="$(wget -qO- "$MOONRAKER_URL/server/spoolman/status" 2>/dev/null || true)"
if ! printf '%s' "$SPOOLMAN_STATUS" | grep -Eq '"spoolman_connected"[[:space:]]*:[[:space:]]*true'; then
    fail "Moonraker не подключён к Spoolman"
fi

echo "Moonraker: доступен"
echo "Spoolman: подключён"

PLUGINS_SCRIPT="$(find_plugins_script 2>/dev/null || true)"
[ -n "$PLUGINS_SCRIPT" ] || fail "штатный Z-Mod plugins.sh не найден"
echo "Z-Mod plugin manager: $PLUGINS_SCRIPT"

# Bootstrap uses raw transport for this one registration helper only. The
# plugin source itself and every later update are delivered by Git.
wget -qO "$HOOK_TMP" "$RAW_BASE/scripts/update_manager_hook.sh?cb=$(date +%s 2>/dev/null || echo $$)" ||
    fail "не удалось загрузить bootstrap helper"
[ -s "$HOOK_TMP" ] || fail "bootstrap helper пуст"
chmod +x "$HOOK_TMP"

AD5X_IFS_ORIGIN="$ORIGIN" \
AD5X_IFS_PRIMARY_BRANCH="$REF" \
AD5X_IFS_UPDATE_CHANNEL="$UPDATE_CHANNEL" \
    "$HOOK_TMP" install

prepare_source_checkout

# Exact current Z-Mod contract: plugins.sh pulls the Git repository, validates
# <plugin>/<plugin>.cfg, calls install.sh and requests Klipper restart.
"$PLUGINS_SCRIPT" "$PLUGIN_NAME" Enable

[ -f "$TARGET_DIR/VERSION" ] || fail "runtime не появился после ENABLE_PLUGIN"
[ -x "$TARGET_DIR/power_on_hook.sh" ] || fail "power_on_hook.sh не установлен"

if fluidd_enabled && [ -x "$TARGET_DIR/install_fluidd_native.sh" ]; then
    echo "Fluidd UI: проверка нативной интеграции..."
    AD5X_IFS_FLUIDD_PATCH_REVISION="$NATIVE_PATCH_REVISION" \
        "$TARGET_DIR/install_fluidd_native.sh" ||
        echo "ПРЕДУПРЕЖДЕНИЕ: native Fluidd пока недоступен; start.sh сохранит legacy fallback." >&2
fi

echo
echo "=== Git-managed установка завершена ==="
echo "Версия runtime: $(cat "$TARGET_DIR/VERSION")"
echo "Git source: $SOURCE_DIR"
echo "Update manager: $PLUGIN_NAME ($UPDATE_CHANNEL)"
echo "Автозапуск: power_on_hook.sh -> mod_data/power_on.sh"
echo "После перезапуска Moonraker обновления появятся в Update Manager."
echo "Проверка состояния: $TARGET_DIR/status.sh"
