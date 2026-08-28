#!/bin/sh
set -eu

RUNTIME="/usr/data/config/mod_data/gcode_3mf_exp"
USER_CONF="/usr/data/config/mod_data/user.moonraker.conf"
MARK_BEGIN="# >>> AD5X GCODE3MF EXPERIMENTAL >>>"
MARK_END="# <<< AD5X GCODE3MF EXPERIMENTAL <<<"

find_component_link() {
    for p in \
        /usr/data/zmod/moonraker/moonraker/components/gcode_3mf.py \
        /usr/data/.mod/.zmod/root/moonraker/moonraker/components/gcode_3mf.py
    do
        [ -e "$p" ] || [ -L "$p" ] || continue
        echo "$p"
        return 0
    done
    return 1
}

if [ -f "$USER_CONF" ]; then
    begin_count="$(grep -Fc "$MARK_BEGIN" "$USER_CONF" || true)"
    end_count="$(grep -Fc "$MARK_END" "$USER_CONF" || true)"
    if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
        echo "Experimental gcode_3mf config markers are damaged or duplicated" >&2
        exit 1
    fi
    if [ "$begin_count" -eq 1 ]; then
        TMP="$USER_CONF.gcode3mf.tmp"
        awk -v begin="$MARK_BEGIN" -v end="$MARK_END" '
            $0 == begin {skip=1; next}
            $0 == end   {skip=0; next}
            !skip {print}
        ' "$USER_CONF" >"$TMP"
        mv "$TMP" "$USER_CONF"
    fi
fi

LINK="$(find_component_link || true)"
if [ -n "$LINK" ]; then
    if [ -L "$LINK" ]; then
        rm -f "$LINK"
    else
        echo "Refusing to remove non-symlink Moonraker component: $LINK" >&2
        exit 1
    fi
fi

echo "Experimental Moonraker 3MF interceptor removed."
echo "Runtime files and backups kept in $RUNTIME"

echo "=== RESTART MOONRAKER ==="
chroot /usr/data/.mod/.zmod /etc/init.d/S65moonraker restart
sleep 3

echo "=== MOONRAKER HEALTH ==="
wget -qO- http://127.0.0.1:7125/server/info || true
echo
