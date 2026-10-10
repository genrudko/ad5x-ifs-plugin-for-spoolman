#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
restore = (ROOT / "scripts" / "restore_fluidd_native.sh").read_text(encoding="utf-8")
uninstall = (ROOT / "scripts" / "uninstall.sh").read_text(encoding="utf-8")
entrypoint = (ROOT / "uninstall.sh").read_text(encoding="utf-8")

# Recovery must not depend on the AD5X host's incomplete curl/wget TLS stack.
assert "/root/moonraker-env/bin/python3" in restore
assert "urllib.request.urlopen" in restore
assert "api.github.com/repos/{repo}/releases/tags/{version}" in restore
assert 'asset.get("digest")' in restore
assert "wget " not in restore
assert "curl " not in restore

# A same-version clean snapshot remains the fast path, but a stale/missing
# snapshot must fall back to an exact-version release download.
assert "clean_fluidd_dir \"$PREVIOUS_DIR\" \"$CURRENT_VERSION\"" in restore
assert "fetching clean same-version Fluidd" in restore
assert "downloaded Fluidd version does not match the installed version" in restore
assert "downloaded Fluidd release identity is invalid" in restore

# Never stop the daemon or remove autostart before Fluidd cleanup succeeds.
restore_pos = uninstall.index('if ! sh "$RESTORE_SCRIPT"; then')
hook_pos = uninstall.index('"$APP_DIR/power_on_hook.sh" remove')
stop_pos = uninstall.index('"$APP_DIR/stop.sh"')
assert restore_pos < hook_pos < stop_pos

# Preserve all user-owned assignment state when uninstall is non-purge.
assert "assignments.json" in uninstall
assert "lane_data_sync.json" in uninstall

# Z-Mod runs root uninstall.sh from fresh Git source, bypassing stale runtime.
assert 'SOURCE_UNINSTALL="$REPO_DIR/scripts/uninstall.sh"' in entrypoint
assert 'sh "$SOURCE_UNINSTALL" --yes' in entrypoint
assert '"$TARGET_DIR/uninstall.sh"' not in entrypoint
assert 'RESTORE_SCRIPT="$SCRIPT_DIR/restore_fluidd_native.sh"' in uninstall
assert 'if ! sh "$RESTORE_SCRIPT"; then' in uninstall
assert 'rm -rf "$WORK_DIR" "$FAILED_DIR"' not in restore
assert 'release asset has no SHA256 digest' in restore

print("robust uninstall Fluidd restore invariants: OK")
