#!/bin/sh
set -eu

CHROOT=/usr/data/.mod/.zmod
RUNTIME_HOST=/usr/data/config/mod_data/gcode_3mf_exp/gcode_3mf.py
RUNTIME_CHROOT=/opt/config/mod_data/gcode_3mf_exp/gcode_3mf.py
BACKUP_DIR=/usr/data/config/mod_data/gcode_3mf_exp
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/gcode_3mf.py.pre-metadata-$TS"

if [ ! -f "$RUNTIME_HOST" ]; then
    echo "GCode3MF runtime not found: $RUNTIME_HOST" >&2
    exit 1
fi

cp -p "$RUNTIME_HOST" "$BACKUP"
echo "backup=$BACKUP"

chroot "$CHROOT" /root/moonraker-env/bin/python3 - <<'PY'
from pathlib import Path

path = Path('/opt/config/mod_data/gcode_3mf_exp/gcode_3mf.py')
text = path.read_text(encoding='utf-8')

if 'async def _ensure_metadata(' not in text:
    marker = '''    @staticmethod\n    def _preflight_summary(preflight: Dict[str, Any]) -> str:\n'''
    if marker not in text:
        raise SystemExit('metadata patch: insertion marker not found')
    method = '''    async def _ensure_metadata(self, cache_relative: str) -> bool:\n        """Populate Moonraker metadata for an extracted hidden G-code file.\n\n        Hidden cache files are created directly on disk, while this Z-Mod\n        installation disables filesystem observation.  Ask Moonraker's own\n        metadata storage to parse the file before Klipper starts it.  Metadata\n        failure is deliberately non-fatal for base 3MF printing.\n        """\n        try:\n            storage = self.file_manager.get_metadata_storage()\n            existing = storage.get(cache_relative, None)\n            if isinstance(existing, dict):\n                logging.info(\n                    "GCode3MF metadata already available hidden=%s thumbnails=%s",\n                    cache_relative,\n                    len(existing.get("thumbnails", []) or []),\n                )\n                return True\n\n            root = self._gcodes_root()\n            cache_path = (root / cache_relative).resolve()\n            if not self._within(root, cache_path) or not cache_path.is_file():\n                raise RuntimeError(f"hidden G-code is unavailable: {cache_relative}")\n\n            path_info = self.file_manager.get_path_info(cache_path, "gcodes")\n            evt = storage.parse_metadata(cache_relative, path_info)\n            await evt.wait()\n            metadata = storage.get(cache_relative, None)\n            if not isinstance(metadata, dict):\n                raise RuntimeError("Moonraker metadata parser returned no metadata")\n\n            logging.info(\n                "GCode3MF metadata ready hidden=%s thumbnails=%s slicer=%s",\n                cache_relative,\n                len(metadata.get("thumbnails", []) or []),\n                metadata.get("slicer", "?"),\n            )\n            return True\n        except Exception:\n            logging.exception(\n                "GCode3MF metadata scan failed hidden=%s", cache_relative\n            )\n            return False\n\n'''
    text = text.replace(marker, method + marker, 1)

call_old = '''            prepared = await loop.run_in_executor(\n                None, self._prepare_sync, filename\n            )\n            ifs_result = await loop.run_in_executor(\n'''
call_new = '''            prepared = await loop.run_in_executor(\n                None, self._prepare_sync, filename\n            )\n            await self._ensure_metadata(prepared["cache_relative"])\n            ifs_result = await loop.run_in_executor(\n'''

if 'await self._ensure_metadata(prepared["cache_relative"])' not in text:
    if call_old not in text:
        raise SystemExit('metadata patch: call marker not found')
    text = text.replace(call_old, call_new, 1)

path.write_text(text, encoding='utf-8')
PY

if ! chroot "$CHROOT" /root/moonraker-env/bin/python3 -m py_compile "$RUNTIME_CHROOT"; then
    echo "py_compile failed; restoring backup" >&2
    cp -p "$BACKUP" "$RUNTIME_HOST"
    exit 1
fi

echo "=== PATCH VERIFY ==="
grep -n -E '_ensure_metadata|GCode3MF metadata ready' "$RUNTIME_HOST"

echo
echo "=== RESTART MOONRAKER ==="
chroot "$CHROOT" /etc/init.d/S65moonraker restart

OK=0
i=0
while [ "$i" -lt 30 ]; do
    if wget -qO /tmp/gcode3mf-metadata-info 'http://127.0.0.1:7125/server/info' 2>/dev/null; then
        STATE="$(chroot "$CHROOT" /root/moonraker-env/bin/python3 - <<'PY'
import json
try:
    data=json.load(open('/tmp/gcode3mf-metadata-info'))['result']
    print(data.get('klippy_state',''))
except Exception:
    print('')
PY
)"
        echo "[$i] klippy_state=$STATE"
        if [ "$STATE" = "ready" ]; then
            OK=1
            break
        fi
    else
        echo "[$i] Moonraker not listening yet"
    fi
    sleep 1
    i=$((i + 1))
done

if [ "$OK" -ne 1 ]; then
    echo "Moonraker/Klipper did not become ready; restoring backup" >&2
    cp -p "$BACKUP" "$RUNTIME_HOST"
    chroot "$CHROOT" /etc/init.d/S65moonraker restart || true
    exit 1
fi

echo
echo "=== COMPONENT LOG ==="
grep -E 'GCode3MF experimental start interceptor installed' /usr/data/logs/moonraker.log | tail -n 3

echo
echo "GCode3MF hidden metadata patch installed."
