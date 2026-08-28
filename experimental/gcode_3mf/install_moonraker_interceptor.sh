#!/bin/sh
set -eu

BRANCH="feature/gcode-3mf-ifs-preflight"
BASE="https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/$BRANCH/experimental/gcode_3mf"
RUNTIME="/usr/data/config/mod_data/gcode_3mf_exp"
USER_CONF="/usr/data/config/mod_data/user.moonraker.conf"
COMPONENT_NAME="gcode_3mf.py"
MARK_BEGIN="# >>> AD5X GCODE3MF EXPERIMENTAL >>>"
MARK_END="# <<< AD5X GCODE3MF EXPERIMENTAL <<<"

find_component_dir() {
    for d in \
        /usr/data/zmod/moonraker/moonraker/components \
        /usr/data/.mod/.zmod/root/moonraker/moonraker/components
    do
        [ -d "$d" ] && { echo "$d"; return 0; }
    done
    return 1
}

COMPONENT_DIR="$(find_component_dir || true)"
[ -n "$COMPONENT_DIR" ] || {
    echo "Moonraker component directory not found" >&2
    exit 1
}

mkdir -p "$RUNTIME"
wget -qO "$RUNTIME/$COMPONENT_NAME" "$BASE/moonraker_gcode_3mf.py?cb=$(date +%s)"
chmod 644 "$RUNTIME/$COMPONENT_NAME"

mkdir -p "$(dirname "$USER_CONF")"
[ -f "$USER_CONF" ] || : >"$USER_CONF"

begin_count="$(grep -Fc "$MARK_BEGIN" "$USER_CONF" || true)"
end_count="$(grep -Fc "$MARK_END" "$USER_CONF" || true)"
if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
    echo "Experimental gcode_3mf config markers are damaged or duplicated" >&2
    exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
cp -p "$USER_CONF" "$RUNTIME/user.moonraker.conf.pre-gcode3mf-$TS"

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

# The absolute symlink target is resolved inside Z-Mod's Moonraker chroot.
ln -sfn "/opt/config/mod_data/gcode_3mf_exp/$COMPONENT_NAME" \
    "$COMPONENT_DIR/gcode_3mf.py"

if [ ! -L "$COMPONENT_DIR/gcode_3mf.py" ]; then
    echo "Moonraker component symlink was not created" >&2
    exit 1
fi

echo "=== INSTALLED EXPERIMENTAL COMPONENT ==="
echo "component_dir=$COMPONENT_DIR"
echo "runtime=$RUNTIME/$COMPONENT_NAME"
echo "config=$USER_CONF"
echo "dry_run=True"
echo

echo "=== RESTART MOONRAKER ==="
chroot /usr/data/.mod/.zmod /etc/init.d/S65moonraker restart

sleep 3

echo
echo "=== MOONRAKER HEALTH ==="
wget -qO- http://127.0.0.1:7125/server/info || true
echo

echo
echo "=== COMPONENT LOG ==="
grep -E 'GCode3MF|gcode_3mf' /usr/data/logs/moonraker.log 2>/dev/null | tail -n 30 || true
