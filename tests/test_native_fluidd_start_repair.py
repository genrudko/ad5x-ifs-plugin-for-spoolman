from pathlib import Path
import re

start = Path('scripts/start.sh').read_text()

assert 'INSTALLED_NATIVE_UPSTREAM' in start, (
    'start.sh must read the upstream tag recorded in ad5x_ifs_native.json'
)
assert 'CURRENT_FLUIDD_UPSTREAM' in start, (
    'start.sh must read the currently installed Fluidd .version'
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

assert 'release_info_version()' in native_installer, (
    'native installer must resolve Fluidd identity from release_info.json'
)
assert 'moonraker_fluidd_version()' in native_installer, (
    'native installer must fall back to Moonraker update_manager version state'
)
assert 'Fluidd .version is missing' not in native_installer, (
    'missing .version alone must not abort native Fluidd repair'
)
assert 'cannot resolve installed Fluidd version from release_info.json, .version, or Moonraker update_manager' in native_installer, (
    'version resolution must fail closed only after all supported identity sources fail'
)
