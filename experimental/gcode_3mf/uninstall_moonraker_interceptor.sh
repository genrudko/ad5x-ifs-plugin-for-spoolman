#!/bin/sh
set -eu

RUNTIME="/usr/data/config/mod_data/gcode_3mf_exp"
USER_CONF="/usr/data/config/mod_data/user.moonraker.conf"
CHROOT="/usr/data/.mod/.zmod"
COMPONENT_NAME="gcode_3mf.py"
MARK_BEGIN="# >>> AD5X GCODE3MF EXPERIMENTAL >>>"
MARK_END="# <<< AD5X GCODE3MF EXPERIMENTAL <<<"

find_component_dir_chroot() {
    chroot "$CHROOT" /bin/sh -c '
        for d in \
            /root/moonraker/moonraker/components \
            /usr/data/zmod/moonraker/moonraker/components \
            /opt/moonraker/moonraker/components
        do
            if [ -d "$d" ]; then
                echo "$d"
                exit 0
            fi
        done
        exit 1
    '
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

COMPONENT_DIR="$(find_component_dir_chroot || true)"
if [ -n "$COMPONENT_DIR" ]; then
    LINK="$COMPONENT_DIR/$COMPONENT_NAME"
    if chroot "$CHROOT" /bin/sh -c '[ -e "$1" ] || [ -L "$1" ]' sh "$LINK"; then
        if chroot "$CHROOT" /bin/sh -c '[ -L "$1" ]' sh "$LINK"; then
            chroot "$CHROOT" /bin/sh -c 'rm -f "$1"' sh "$LINK"
        else
            echo "Refusing to remove non-symlink Moonraker component: $LINK" >&2
            exit 1
        fi
    fi
fi

echo "Experimental Moonraker 3MF interceptor removed."
echo "Runtime files and backups kept in $RUNTIME"
echo "=== RESTART MOONRAKER ==="
chroot "$CHROOT" /etc/init.d/S65moonraker restart
sleep 3

echo "=== MOONRAKER HEALTH ==="
wget -qO- http://127.0.0.1:7125/server/info || true
echo
