#!/bin/sh
set -eu

HELPER_COMMIT="892b0fb3efeeac9dd09d342a79077f6dd1e426f5"
BASE="https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/$HELPER_COMMIT/experimental/gcode_3mf"
CHROOT="/usr/data/.mod/.zmod"
RUNTIME="/usr/data/config/mod_data/gcode_3mf_exp"
CHROOT_RUNTIME="/opt/config/mod_data/gcode_3mf_exp"
USER_CONF="/usr/data/config/mod_data/user.moonraker.conf"
COMPONENT_DIR="/root/moonraker-env/moonraker/components"
COMPONENT_NAME="gcode_3mf_upload_bridge.py"
MARK_BEGIN="# >>> AD5X GCODE3MF UPLOAD BRIDGE EXPERIMENTAL >>>"
MARK_END="# <<< AD5X GCODE3MF UPLOAD BRIDGE EXPERIMENTAL <<<"

[ -d "$CHROOT" ] || { echo "Z-Mod chroot not found: $CHROOT" >&2; exit 1; }
if ! chroot "$CHROOT" /bin/sh -c '[ -d "$1" ]' sh "$COMPONENT_DIR"; then
    echo "Moonraker component directory not found: $COMPONENT_DIR" >&2
    exit 1
fi

mkdir -p "$RUNTIME"
wget -qO "$RUNTIME/$COMPONENT_NAME" "$BASE/moonraker_gcode_3mf_upload_bridge.py"
chmod 644 "$RUNTIME/$COMPONENT_NAME"

chroot "$CHROOT" /root/moonraker-env/bin/python3 -m py_compile \
    "$CHROOT_RUNTIME/$COMPONENT_NAME"

mkdir -p "$(dirname "$USER_CONF")"
[ -f "$USER_CONF" ] || : >"$USER_CONF"

begin_count="$(grep -Fc "$MARK_BEGIN" "$USER_CONF" || true)"
end_count="$(grep -Fc "$MARK_END" "$USER_CONF" || true)"
if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
    echo "Upload bridge config markers are damaged or duplicated" >&2
    exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="$RUNTIME/user.moonraker.conf.pre-upload-bridge-$TS"
cp -p "$USER_CONF" "$BACKUP"

TMP="$USER_CONF.gcode3mf-upload.tmp"
awk -v begin="$MARK_BEGIN" -v end="$MARK_END" '
    $0 == begin {skip=1; next}
    $0 == end   {skip=0; next}
    !skip {print}
' "$USER_CONF" >"$TMP"
cat >>"$TMP" <<'EOF'

# >>> AD5X GCODE3MF UPLOAD BRIDGE EXPERIMENTAL >>>
[gcode_3mf_upload_bridge]
# <<< AD5X GCODE3MF UPLOAD BRIDGE EXPERIMENTAL <<<
EOF
mv "$TMP" "$USER_CONF"

LINK="$COMPONENT_DIR/$COMPONENT_NAME"
if chroot "$CHROOT" /bin/sh -c '[ -e "$1" ] && [ ! -L "$1" ]' sh "$LINK"; then
    cp -p "$BACKUP" "$USER_CONF"
    echo "Refusing to replace non-symlink Moonraker component: $LINK" >&2
    exit 1
fi
chroot "$CHROOT" /bin/sh -c 'ln -sfn "$1" "$2"' sh \
    "$CHROOT_RUNTIME/$COMPONENT_NAME" "$LINK"

rollback() {
    echo "Upload bridge failed to load; rolling back." >&2
    cp -p "$BACKUP" "$USER_CONF" || true
    chroot "$CHROOT" /bin/sh -c 'if [ -L "$1" ]; then rm -f "$1"; fi' sh "$LINK" || true
    chroot "$CHROOT" /etc/init.d/S65moonraker restart || true
    sleep 3
}
trap rollback HUP INT TERM

printf '%s\n' "=== RESTART MOONRAKER ==="
chroot "$CHROOT" /etc/init.d/S65moonraker restart

healthy=0
i=0
while [ "$i" -lt 12 ]; do
    if wget -qO /tmp/gcode3mf-upload-server-info http://127.0.0.1:7125/server/info 2>/dev/null; then
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

if ! grep -q 'GCode3MF upload bridge enabled' /usr/data/logs/moonraker.log 2>/dev/null; then
    echo "Moonraker is healthy but upload bridge load marker is missing." >&2
    rollback
    trap - HUP INT TERM
    exit 1
fi

trap - HUP INT TERM

echo "=== MOONRAKER HEALTH ==="
cat /tmp/gcode3mf-upload-server-info
echo
echo "=== UPLOAD BRIDGE LOG ==="
grep -E 'GCode3MF upload bridge|gcode_3mf_upload_bridge' /usr/data/logs/moonraker.log 2>/dev/null | tail -n 20 || true
echo
echo "GCode3MF upload bridge installed. Existing gcode_3mf remains dry_run=True."
