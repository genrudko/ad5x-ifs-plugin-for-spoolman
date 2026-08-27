#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
POWER_ON="/usr/data/config/mod_data/power_on.sh"
BEGIN_MARKER="# >>> AD5X IFS Plugin for Spoolman >>>"
END_MARKER="# <<< AD5X IFS Plugin for Spoolman <<<"
TMP="${POWER_ON}.ifs-spoolman.$$"

cleanup() {
    rm -f "$TMP"
}
trap cleanup EXIT HUP INT TERM

ensure_power_on() {
    mkdir -p "${POWER_ON%/*}"
    if [ ! -f "$POWER_ON" ]; then
        printf '%s\n' '#!/bin/sh' >"$POWER_ON"
    fi
}

strip_managed_block() {
    awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
        $0 == begin {
            if (skip) exit 3
            skip = 1
            found_begin = 1
            next
        }
        $0 == end {
            if (!skip) exit 3
            skip = 0
            found_end = 1
            next
        }
        !skip { print }
        END {
            if (skip || (found_begin && !found_end)) exit 3
        }
    ' "$POWER_ON" >"$TMP" || {
        echo "$APP_NAME: повреждён управляемый блок в $POWER_ON" >&2
        rm -f "$TMP"
        return 1
    }

    cat "$TMP" >"$POWER_ON"
    rm -f "$TMP"
}

install_hook() {
    ensure_power_on
    strip_managed_block

    cat >>"$POWER_ON" <<'EOF'

# >>> AD5X IFS Plugin for Spoolman >>>
AD5X_IFS_START="/usr/data/config/mod_data/ifs_spoolman/start.sh"
AD5X_IFS_BOOT_LOG="/usr/data/config/mod_data/ifs_spoolman/boot.log"
if [ -x "$AD5X_IFS_START" ]; then
    "$AD5X_IFS_START" >>"$AD5X_IFS_BOOT_LOG" 2>&1 &
fi
# <<< AD5X IFS Plugin for Spoolman <<<
EOF

    chmod +x "$POWER_ON" 2>/dev/null || true
    echo "$APP_NAME: автозапуск зарегистрирован в $POWER_ON"
}

remove_hook() {
    [ -f "$POWER_ON" ] || return 0
    strip_managed_block
    chmod +x "$POWER_ON" 2>/dev/null || true
    echo "$APP_NAME: автозапуск удалён из $POWER_ON"
}

check_hook() {
    [ -f "$POWER_ON" ] || exit 1
    grep -Fqx "$BEGIN_MARKER" "$POWER_ON" &&
        grep -Fqx "$END_MARKER" "$POWER_ON"
}

case "${1:-install}" in
    install) install_hook ;;
    remove) remove_hook ;;
    check) check_hook ;;
    *)
        echo "Usage: $0 {install|remove|check}" >&2
        exit 2
        ;;
esac
