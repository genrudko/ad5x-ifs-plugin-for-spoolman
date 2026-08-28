#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
PLUGIN_NAME="ad5x_ifs_spoolman"
CONF="/usr/data/config/mod_data/user.moonraker.conf"
BEGIN_MARKER="# >>> AD5X IFS Spoolman update manager >>>"
END_MARKER="# <<< AD5X IFS Spoolman update manager <<<"
SECTION="[update_manager $PLUGIN_NAME]"
ORIGIN="${AD5X_IFS_ORIGIN:-https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git}"
PRIMARY_BRANCH="${AD5X_IFS_PRIMARY_BRANCH:-release/standalone-0.6.x}"
# Z-Mod's stable plugin channel resets to the globally latest tag. This repo
# also has non-version tags, so production follows the controlled release branch
# through Moonraker's dev branch-tracking mode.
CHANNEL="${AD5X_IFS_UPDATE_CHANNEL:-dev}"
MOONRAKER_PATH="/root/printer_data/config/mod_data/plugins/$PLUGIN_NAME"

fail() {
    echo "$APP_NAME: $*" >&2
    exit 1
}

count_exact() {
    NEEDLE="$1"
    [ -f "$CONF" ] || {
        echo 0
        return 0
    }
    grep -Fxc "$NEEDLE" "$CONF" 2>/dev/null || true
}

validate_marker_state() {
    BEGIN_COUNT="$(count_exact "$BEGIN_MARKER")"
    END_COUNT="$(count_exact "$END_MARKER")"
    SECTION_COUNT="$(count_exact "$SECTION")"

    if [ "$BEGIN_COUNT" -eq 0 ] && [ "$END_COUNT" -eq 0 ]; then
        [ "$SECTION_COUNT" -eq 0 ] ||
            fail "$SECTION уже существует вне управляемого блока; автоматическая перезапись запрещена"
        return 0
    fi

    [ "$BEGIN_COUNT" -eq 1 ] && [ "$END_COUNT" -eq 1 ] && [ "$SECTION_COUNT" -eq 1 ] ||
        fail "повреждён или дублирован управляемый update_manager block; автоматическая перезапись запрещена"
}

has_managed_block() {
    [ -f "$CONF" ] || return 1
    [ "$(count_exact "$BEGIN_MARKER")" -eq 1 ] &&
        [ "$(count_exact "$END_MARKER")" -eq 1 ] &&
        [ "$(count_exact "$SECTION")" -eq 1 ]
}

strip_managed_block() {
    INPUT="$1"
    OUTPUT="$2"
    awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
        $0 == begin { skip = 1; next }
        $0 == end { skip = 0; next }
        !skip { print }
    ' "$INPUT" >"$OUTPUT"
}

replace_conf_without_block() {
    mkdir -p "${CONF%/*}"
    [ -f "$CONF" ] || : >"$CONF"
    validate_marker_state

    CLEAN="$CONF.ifs-clean.$$"
    NEW="$CONF.ifs-new.$$"
    trap 'rm -f "$CLEAN" "$NEW"' EXIT HUP INT TERM

    strip_managed_block "$CONF" "$CLEAN"
    cp -p "$CONF" "$NEW" 2>/dev/null || cp "$CONF" "$NEW"
    cat "$CLEAN" >"$NEW"
    mv "$NEW" "$CONF"
    rm -f "$CLEAN"
    trap - EXIT HUP INT TERM
}

install_block() {
    mkdir -p "${CONF%/*}"
    [ -f "$CONF" ] || : >"$CONF"
    validate_marker_state
    replace_conf_without_block

    if [ -s "$CONF" ]; then
        printf '\n' >>"$CONF"
    fi

    cat >>"$CONF" <<EOF
$BEGIN_MARKER
$SECTION
type: git_repo
channel: $CHANNEL
path: $MOONRAKER_PATH
origin: $ORIGIN
is_system_service: False
primary_branch: $PRIMARY_BRANCH
$END_MARKER
EOF

    echo "$APP_NAME: Moonraker update_manager зарегистрирован."
    echo "Channel: $CHANNEL"
    echo "Branch: $PRIMARY_BRANCH"
}

remove_block() {
    [ -f "$CONF" ] || {
        echo "$APP_NAME: user.moonraker.conf отсутствует; удалять нечего."
        exit 0
    }
    validate_marker_state
    if ! has_managed_block; then
        echo "$APP_NAME: управляемый update_manager block отсутствует."
        exit 0
    fi
    replace_conf_without_block
    echo "$APP_NAME: Moonraker update_manager block удалён."
}

check_block() {
    validate_marker_state
    has_managed_block || return 1
    grep -Fqx "type: git_repo" "$CONF" || return 1
    grep -Fqx "path: $MOONRAKER_PATH" "$CONF" || return 1
    grep -Fqx "origin: $ORIGIN" "$CONF" || return 1
}

case "${1:-}" in
    install) install_block ;;
    remove) remove_block ;;
    present) has_managed_block ;;
    check) check_block ;;
    *)
        echo "Usage: $0 {install|remove|present|check}" >&2
        exit 2
        ;;
esac
