#!/bin/sh
set -eu

REPO_OWNER="genrudko"
REPO_NAME="ad5x-ifs-plugin-for-spoolman"
REF="main"
WORK_DIR="/usr/data/ad5x-ifs-plugin-installer"
ARCHIVE="$WORK_DIR/source.tar.gz"
SOURCE_DIR="$WORK_DIR/$REPO_NAME-$REF"
MOONRAKER_URL="http://127.0.0.1:7125"

fail() {
    echo "ОШИБКА: $*" >&2
    exit 1
}

echo "=== AD5X IFS Plugin for Spoolman — установка для чистого Z-Mod ==="

[ "$(id -u)" = "0" ] || fail "скрипт нужно запускать по SSH от root"
command -v wget >/dev/null 2>&1 || fail "в системе не найден wget"
command -v gzip >/dev/null 2>&1 || fail "в системе не найден gzip"
command -v tar >/dev/null 2>&1 || fail "в системе не найден tar"

if ! wget -qO- "$MOONRAKER_URL/server/info" >/dev/null 2>&1; then
    fail "Moonraker недоступен по $MOONRAKER_URL. Проверьте установку и запуск Z-Mod"
fi

SPOOLMAN_STATUS="$(wget -qO- "$MOONRAKER_URL/server/spoolman/status" 2>/dev/null || true)"

if ! printf '%s' "$SPOOLMAN_STATUS" | grep -Eq '"spoolman_connected"[[:space:]]*:[[:space:]]*true'; then
    cat >&2 <<'EOF'
ОШИБКА: Moonraker не подключён к Spoolman.

Плагин не заменяет Spoolman и не устанавливает его автоматически.
Перед установкой плагина обязательно:

1. установить и запустить Spoolman на ПК, NAS, VPS или другом сервере;
2. добавить в moonraker.conf:

   [spoolman]
   server: http://IP_СЕРВЕРА_SPOOLMAN:7912

3. перезапустить Moonraker;
4. убедиться, что /server/spoolman/status возвращает
   "spoolman_connected": true.

Подробности находятся в docs/spoolman_RU.md репозитория.
EOF
    exit 1
fi

echo "Moonraker: доступен"
echo "Spoolman: подключён"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

URL="https://codeload.github.com/$REPO_OWNER/$REPO_NAME/tar.gz/refs/heads/$REF"

echo "Загрузка репозитория..."
wget -O "$ARCHIVE" "$URL"

echo "Распаковка средствами BusyBox..."
gzip -dc "$ARCHIVE" | tar -C "$WORK_DIR" -xf -

[ -f "$SOURCE_DIR/install.sh" ] || fail "в загруженном репозитории отсутствует install.sh"

chmod +x "$SOURCE_DIR/install.sh" "$SOURCE_DIR/update.sh" "$SOURCE_DIR"/scripts/*.sh

cd "$SOURCE_DIR"
./install.sh

rm -rf "$WORK_DIR"

echo
echo "=== Установка завершена ==="
echo "Откройте: http://IP_ПРИНТЕРА:7913/"
echo "Проверка состояния:"
echo "/usr/data/config/mod_data/ifs_spoolman/status.sh"
