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
assert '"2b3e766481520d7d91d7a53d11ab17b0d0b8cec36d4b955074e0da5e250ddfbb"' in restore
assert "Using pinned upstream SHA256" in restore
assert "no GitHub API request" in restore
assert "downloaded Fluidd .version conflicts" in restore

import os
import subprocess
import tempfile

# Run the actual Z-Mod entrypoint in a temporary simulated installation:
# the installed runtime has a deliberately stale uninstall.sh, while the Git
# source has a new one.  Verify source wins even when runtime still exists.
with tempfile.TemporaryDirectory(prefix="ad5x-uninstall-check-") as tmp:
    simulation = Path(tmp)
    runtime = simulation / "installed-runtime"
    runtime.mkdir()
    source_scripts = simulation / "scripts"
    source_scripts.mkdir()
    marker = simulation / "invoked"
    old_runtime_helper = runtime / "uninstall.sh"
    old_runtime_helper.write_text(
        '#!/bin/sh\necho STALE > "$TEST_MARKER"\nexit 9\n', encoding="utf-8"
    )

    installed_entrypoint = simulation / "uninstall.sh"
    installed_entrypoint.write_text(
        entrypoint.replace(
            'TARGET_DIR="/usr/data/config/mod_data/ifs_spoolman"',
            f'TARGET_DIR="{runtime}"',
        ).replace(
            'CFG="/usr/data/config/mod_data/plugins.cfg"',
            f'CFG="{simulation / "plugins.cfg"}"',
        ),
        encoding="utf-8",
    )

    source_helper = source_scripts / "uninstall.sh"
    source_helper.write_text(
        '#!/bin/sh\necho FRESH > "$TEST_MARKER"\nexit 0\n',
        encoding="utf-8",
    )
    env = dict(os.environ, TEST_MARKER=str(marker))
    ok = subprocess.run(["sh", str(installed_entrypoint)], env=env, capture_output=True)
    assert ok.returncode == 0, ok.stderr
    assert marker.read_text().strip() == "FRESH"

    # On failure Z-Mod has already removed the include before calling this
    # entrypoint. Make sure the source entrypoint restores it.
    (simulation / "ad5x_ifs_spoolman.cfg").write_text(
        "# fixture\n", encoding="utf-8"
    )
    (simulation / "plugins.cfg").write_text(
        "# user config\n", encoding="utf-8"
    )
    source_helper.write_text(
        '#!/bin/sh\nexit 7\n', encoding="utf-8"
    )
    bad = subprocess.run(["sh", str(installed_entrypoint)], env=env, capture_output=True)
    assert bad.returncode != 0
    include = "[include plugins/ad5x_ifs_spoolman/ad5x_ifs_spoolman.cfg]"
    assert include in (simulation / "plugins.cfg").read_text()

import tempfile
import subprocess
import os

# Execute the production snapshot validator in a disposable shell environment.
# A stock Moonraker web deployment may have release_info.json, not .version.
func_source = restore.split('[ "$(id -u)" = "0" ]')[0]
with tempfile.TemporaryDirectory(prefix="fluidd-snapshot-test-") as test_dir:
    d = Path(test_dir) / "clean"
    d.mkdir()
    (d / "index.html").write_text("<html>Stock Fluidd</html>")
    (d / "release_info.json").write_text(
        '{"project_owner":"ghzserg","project_name":"fluidd","version":"v1.37.7"}'
    )
    validation = (
        func_source
        + "\nclean_fluidd_dir \"$1\" \"$2\"\n"
    )
    def check(expected_version):
        return subprocess.run(
            ["sh", "-c", validation, "snapshot-check", str(d), expected_version],
            capture_output=True,
            text=True
        ).returncode

    assert check("v1.37.7") == 0, "matching stock backup without .version rejected"
    assert check("v1.37.6") != 0, "wrong-version snapshot accepted"
    (d / ".version").write_text("v1.37.6")
    assert check("v1.37.7") != 0, "conflicting explicit .version accepted"
    (d / ".version").unlink()
    (d / "ad5x_ifs_native.json").write_text('{"patch_revision":10}')
    assert check("v1.37.7") != 0, "plugin-patched backup accepted"
    (d / "ad5x_ifs_native.json").unlink()
    (d / "release_info.json").write_text(
        '{"project_owner":"wrong","project_name":"fluidd","version":"v1.37.7"}'
    )
    assert check("v1.37.7") != 0, "wrong owner accepted"
    (d / "release_info.json").unlink()
    assert check("v1.37.7") != 0, "missing release identity accepted"

print("robust uninstall Fluidd restore invariants: OK")
