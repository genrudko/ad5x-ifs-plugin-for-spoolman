from pathlib import Path
import re
import subprocess
import tempfile

start = Path('scripts/start.sh').read_text()

assert 'INSTALLED_NATIVE_UPSTREAM' in start, (
    'start.sh must read the upstream tag recorded in ad5x_ifs_native.json'
)
assert 'CURRENT_FLUIDD_UPSTREAM' in start, (
    'start.sh must resolve the currently installed Fluidd version'
)
assert 'release_info.json' in start, (
    'start.sh must fall back to Fluidd release_info.json when .version is absent'
)
assert re.search(
    r'INSTALLED_NATIVE_PATCH.*NATIVE_PATCH_REVISION.*\|\|.*INSTALLED_NATIVE_UPSTREAM.*CURRENT_FLUIDD_UPSTREAM',
    start,
    re.S,
), (
    'native Fluidd repair must run when either patch revision or upstream Fluidd '
    'version changed'
)
boot = Path('scripts/boot_start.sh').read_text()
native_installer = Path('scripts/install_fluidd_native.sh').read_text()

assert '"$APP_DIR/install_fluidd_card.sh"' not in boot, (
    'boot_start.sh must never automatically reinstall the historical Fluidd DOM injection'
)
assert '"$APP_DIR/uninstall_fluidd_card.sh"' in boot, (
    'boot_start.sh must remove stale legacy injection once a native marker exists'
)
assert "existing UI state is preserved" in boot, (
    'failed native migration must not delete the currently working Fluidd UI'
)
assert 'legacy automatic fallback is disabled' in start, (
    'native repair failure must be fail-closed instead of restoring legacy injection'
)
assert 'ZMOD_ROOT="/usr/data/.mod/.zmod"' in native_installer, (
    'native installer must use the documented AD5X Z-Mod chroot root'
)
assert 'ZMOD_SOURCE_REPO="/opt/config/mod_data/plugins/ad5x_ifs_spoolman"' in native_installer, (
    'native installer must use the documented plugin checkout path inside Z-Mod chroot'
)
assert 'chroot "$ZMOD_ROOT" git -C "$ZMOD_SOURCE_REPO" fetch' in native_installer, (
    'git transport must run inside the Z-Mod chroot, not the Moonraker process root'
)
assert 'chroot "$ROOT" git -C' not in native_installer, (
    'native installer must not mix Moonraker process root with Z-Mod plugin paths'
)

assert 'fluidd_version_from_dir' in native_installer, (
    'native installer must resolve Fluidd identity through a dedicated helper'
)
assert 'release_info.json' in native_installer, (
    'native installer must accept valid ghzserg/fluidd release metadata when .version is absent'
)
assert 'Fluidd .version is missing' not in native_installer, (
    'missing .version alone must not abort native installation'
)

def extract_function(script: str, name: str) -> str:
    match = re.search(
        rf'^{re.escape(name)}\(\) \{{\n.*?^\}}\n',
        script,
        re.M | re.S,
    )
    assert match, f'{name} function not found'
    return match.group(0)


def run_version_helper(script: str, fixture: Path):
    function = extract_function(script, 'fluidd_version_from_dir')
    return subprocess.run(
        ['sh', '-c', function + '\nfluidd_version_from_dir "$1"', 'sh', str(fixture)],
        check=False,
        text=True,
        capture_output=True,
    )


for script_name, script_text in (
    ('start.sh', start),
    ('install_fluidd_native.sh', native_installer),
):
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)

        (fixture / 'release_info.json').write_text(
            '{"project_name":"fluidd","project_owner":"ghzserg","version":"v1.37.6"}\n'
        )
        result = run_version_helper(script_text, fixture)
        assert result.returncode == 0, (
            f'{script_name} must resolve Fluidd from release_info.json without .version: '
            f'{result.stderr}'
        )
        assert result.stdout.strip() == 'v1.37.6', (
            f'{script_name} resolved unexpected release_info version: {result.stdout!r}'
        )

        (fixture / '.version').write_text('v1.37.5\n')
        result = run_version_helper(script_text, fixture)
        assert result.returncode == 0
        assert result.stdout.strip() == 'v1.37.5', (
            f'{script_name} must prefer .version when both identity sources exist'
        )

        (fixture / '.version').unlink()
        (fixture / 'release_info.json').write_text(
            '{"project_name":"fluidd","project_owner":"someone-else","version":"v1.37.6"}\n'
        )
        result = run_version_helper(script_text, fixture)
        assert result.returncode != 0 or not result.stdout.strip(), (
            f'{script_name} must reject release metadata from the wrong project owner'
        )

