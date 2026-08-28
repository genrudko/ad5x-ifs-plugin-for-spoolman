#!/bin/sh
set -eu

BRANCH="feature/gcode-3mf-ifs-preflight"
BASE="https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/$BRANCH/experimental/gcode_3mf"
RUNTIME="/usr/data/config/mod_data/gcode_3mf_exp"
USER_CONF="/usr/data/config/mod_data/user.moonraker.conf"
CHROOT="/usr/data/.mod/.zmod"
COMPONENT_NAME="gcode_3mf.py"
CHROOT_RUNTIME="/opt/config/mod_data/gcode_3mf_exp"
MARK_BEGIN="# >>> AD5X GCODE3MF EXPERIMENTAL >>>"
MARK_END="# <<< AD5X GCODE3MF EXPERIMENTAL <<<"

[ -d "$CHROOT" ] || {
    echo "Z-Mod chroot not found: $CHROOT" >&2
    exit 1
}

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

COMPONENT_DIR="$(find_component_dir_chroot || true)"
[ -n "$COMPONENT_DIR" ] || {
    echo "Moonraker component directory not found inside live Z-Mod chroot" >&2
    echo "Checked: /root/moonraker/moonraker/components, /usr/data/zmod/moonraker/moonraker/components, /opt/moonraker/moonraker/components" >&2
    exit 1
}

COMPONENT_LINK="$COMPONENT_DIR/$COMPONENT_NAME"

if chroot "$CHROOT" /bin/sh -c '[ -e "$1" ] && [ ! -L "$1" ]' sh "$COMPONENT_LINK"; then
    echo "Refusing to replace non-symlink Moonraker component: $COMPONENT_LINK" >&2
    exit 1
fi

mkdir -p "$RUNTIME"
wget -qO "$RUNTIME/$COMPONENT_NAME" "$BASE/moonraker_gcode_3mf.py?cb=$(date +%s)"
chmod 644 "$RUNTIME/$COMPONENT_NAME"

if ! chroot "$CHROOT" /bin/sh -c '[ -f "$1" ]' sh "$CHROOT_RUNTIME/$COMPONENT_NAME"; then
    echo "Experimental component is not visible inside Z-Mod chroot" >&2
    exit 1
fi

# Catch syntax errors before touching Moonraker configuration.
chroot "$CHROOT" /root/moonraker-env/bin/python3 -m py_compile \
    "$CHROOT_RUNTIME/$COMPONENT_NAME"

mkdir -p "$(dirname "$USER_CONF")"
[ -f "$USER_CONF" ] || : >"$USER_CONF"

begin_count="$(grep -Fc "$MARK_BEGIN" "$USER_CONF" || true)"
end_count="$(grep -Fc "$MARK_END" "$USER_CONF" || true)"
if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
    echo "Experimental gcode_3mf config markers are damaged or duplicated" >&2
    exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="$RUNTIME/user.moonraker.conf.pre-gcode3mf-$TS"
cp -p "$USER_CONF" "$BACKUP"

TMP="$USER_CONF.gcode3mf.tmp"
awk -v begin="$MARK_BEGIN" -v end="$MARK_END" '
    $0 == begin {skip=1; next}
    $0 == end   {skip=0; next}
    !skip {print}
' "$USER_CONF" >"$TMP"

cat >>"$TMP" <<'EOF'

# >>> AD5X GCODE3MF EXPERIMENTAL >>>
[gcode_3mf]
dry_run: True
block_on_ifs_mismatch: True
ifs_preflight_url: http://127.0.0.1:7913
cache_subdir: .zmod/gcode_3mf
# <<< AD5X GCODE3MF EXPERIMENTAL <<<
EOF
mv "$TMP" "$USER_CONF"

# Create the link from inside the same chroot Moonraker runs in.  This avoids
# assuming which host-side path backs /root/moonraker on a particular Z-Mod build.
chroot "$CHROOT" /bin/sh -c 'ln -sfn "$1" "$2"' sh \
    "$CHROOT_RUNTIME/$COMPONENT_NAME" "$COMPONENT_LINK"

if ! chroot "$CHROOT" /bin/sh -c '[ -L "$1" ]' sh "$COMPONENT_LINK"; then
    cp -p "$BACKUP" "$USER_CONF"
    echo "Moonraker component symlink was not created" >&2
    exit 1
fi

rollback() {
    echo "Experimental Moonraker component failed to load; rolling back." >&2
    cp -p "$BACKUP" "$USER_CONF" || true
    chroot "$CHROOT" /bin/sh -c '
        if [ -L "$1" ]; then rm -f "$1"; fi
    ' sh "$COMPONENT_LINK" || true
    chroot "$CHROOT" /etc/init.d/S65moonraker restart || true
    sleep 3
    tail -n 100 /usr/data/logs/moonraker.log 2>/dev/null || true
}

trap rollback HUP INT TERM

echo "=== INSTALLED EXPERIMENTAL COMPONENT ==="
echo "component_dir(chroot)=$COMPONENT_DIR"
echo "runtime=$RUNTIME/$COMPONENT_NAME"
echo "config=$USER_CONF"
echo "backup=$BACKUP"
echo "dry_run=True"
echo

echo "=== RESTART MOONRAKER ==="
chroot "$CHROOT" /etc/init.d/S65moonraker restart

healthy=0
i=0
while [ "$i" -lt 12 ]; do
    if wget -qO /tmp/gcode3mf-server-info http://127.0.0.1:7125/server/info 2>/dev/null; then
        healthy=1
        break
    fi
    sleep 1
    i=$((i + 1))
done

if [ "$healthy" -ne 1 ]; then
    rollback
    trap - HUP INT TERM
    exit 1
fi

if ! grep -q 'GCode3MF experimental start interceptor installed' /usr/data/logs/moonraker.log 2>/dev/null; then
    echo "Moonraker is healthy but gcode_3mf load marker is missing." >&2
    rollback
    trap - HUP INT TERM
    exit 1
fi

trap - HUP INT TERM

echo
echo "=== MOONRAKER HEALTH ==="
cat /tmp/gcode3mf-server-info
echo

echo
echo "=== COMPONENT LOG ==="
grep -E 'GCode3MF|gcode_3mf' /usr/data/logs/moonraker.log 2>/dev/null | tail -n 30 || true

echo
echo "GCode3MF experimental start interceptor installed in DRY-RUN mode."
