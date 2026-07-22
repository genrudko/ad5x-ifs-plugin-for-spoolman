#!/bin/sh
set -eu

REPO_OWNER="genrudko"
REPO_NAME="ad5x-ifs-plugin-for-spoolman"
REF="feature/filament-manager-clean"
RAW_BASE="https://raw.githubusercontent.com/$REPO_OWNER/$REPO_NAME/$REF"
CACHE_BUSTER="$(date +%s 2>/dev/null || echo "$$")"
WORK_DIR="/usr/data/ad5x-ifs-plugin-installer"
SOURCE_DIR="$WORK_DIR/source"
TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"
MOONRAKER_URL="http://127.0.0.1:7125"

fail() { echo "ОШИБКА: $*" >&2; exit 1; }
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT HUP INT TERM

download_file() {
    REMOTE_PATH="$1"
    LOCAL_PATH="$SOURCE_DIR/$REMOTE_PATH"
    LOCAL_DIR="${LOCAL_PATH%/*}"
    mkdir -p "$LOCAL_DIR"
    echo "  $REMOTE_PATH"
    wget -qO "$LOCAL_PATH" "$RAW_BASE/$REMOTE_PATH?cb=$CACHE_BUSTER" || {
        rm -f "$LOCAL_PATH"
        fail "не удалось загрузить $REMOTE_PATH"
    }
    [ -s "$LOCAL_PATH" ] || fail "загружен пустой файл: $REMOTE_PATH"
}

echo "=== AD5X IFS Manager — combined local + Spoolman view ==="
[ "$(id -u)" = "0" ] || fail "скрипт нужно запускать по SSH от root"
command -v wget >/dev/null 2>&1 || fail "в системе не найден wget"
if ! wget -qO- "$MOONRAKER_URL/server/info" >/dev/null 2>&1; then
    fail "Moonraker недоступен по $MOONRAKER_URL. Проверьте установку и запуск Z-Mod"
fi

echo "Moonraker: доступен"
SPOOLMAN_STATUS="$(wget -qO- "$MOONRAKER_URL/server/spoolman/status" 2>/dev/null || true)"
if printf '%s' "$SPOOLMAN_STATUS" | grep -Eq '"spoolman_connected"[[:space:]]*:[[:space:]]*true'; then
    echo "Spoolman: подключён; режим auto выберет провайдер spoolman"
else
    echo "Spoolman: не подключён; режим auto выберет локальный провайдер Z-Mod"
fi

rm -rf "$WORK_DIR"
mkdir -p "$SOURCE_DIR"
echo "Загрузка файлов ветки $REF..."

for FILE in \
    install.sh \
    update.sh \
    VERSION \
    PACKAGE_MANIFEST.txt \
    plugin/ifs_spoolman.py \
    plugin/ifs_spoolman_runtime.py \
    plugin/ifs_spoolman_writer.py \
    plugin/ifs_spoolman_ui.py \
    plugin/ifs_spoolman_local.py \
    plugin/ifs_spoolman_control.py \
    plugin/ifs_spoolman_planner.py \
    plugin/zmod-filaments.html \
    plugin/zmod-filaments-live.js \
    plugin/zmod-inventory-provider.js \
    plugin/zmod-combined-inventory.js \
    plugin/ui_v0_2.html \
    plugin/ifs-spoolman-card.js \
    plugin/ifs-spoolman-layout.js \
    plugin/ifs-spoolman-dashboard.js \
    plugin/ifs-spoolman-visibility.js \
    plugin/ifs-spoolman-selection.js \
    plugin/ifs-spoolman-controls.js \
    scripts/boot_start.sh \
    scripts/start.sh \
    scripts/stop.sh \
    scripts/status.sh \
    scripts/update.sh \
    scripts/uninstall.sh \
    scripts/install_fluidd_card.sh \
    scripts/uninstall_fluidd_card.sh \
    examples/config.example.json \
    examples/assignments.example.json \
    examples/inventory.example.json

do
    download_file "$FILE"
done

chmod +x "$SOURCE_DIR/install.sh" "$SOURCE_DIR/update.sh" "$SOURCE_DIR"/scripts/*.sh
cd "$SOURCE_DIR"

if [ -d "$TARGET_DIR" ] && [ -f "$TARGET_DIR/ifs_spoolman.py" ]; then
    echo "Обнаружена существующая установка: выполняется безопасное обновление."
    ./update.sh --dry-run
    ./update.sh
    RESULT_TEXT="Обновление завершено"
else
    echo "Существующая установка не обнаружена: выполняется новая установка."
    ./install.sh
    RESULT_TEXT="Установка завершена"
fi

echo
echo "=== $RESULT_TEXT ==="
echo "Ветка разработки: $REF"
echo "Версия: $(cat "$TARGET_DIR/VERSION")"
echo "Провайдеры учёта: auto, local, spoolman, none."
echo "Комбинированное отображение локальных данных и Spoolman доступно в менеджере."
echo "Read-only readiness API: http://IP_ПРИНТЕРА:7913/api/ifs/control/readiness"
echo "Read-only operation plan API: http://IP_ПРИНТЕРА:7913/api/ifs/control/plan?action=unload"
echo "Менеджер: http://IP_ПРИНТЕРА:7913/manager"
