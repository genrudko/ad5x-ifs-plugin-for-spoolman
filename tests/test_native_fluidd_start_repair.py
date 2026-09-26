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
    'boot_start.sh must actively remove stale legacy Fluidd injection'
)
assert 'legacy automatic fallback is disabled' in start, (
    'native repair failure must be fail-closed instead of restoring legacy injection'
)
assert 'CHROOT_SOURCE_REPO="/opt/config/mod_data/plugins/ad5x_ifs_spoolman"' in native_installer, (
    'native installer must use the actual plugin checkout path inside the Z-Mod chroot'
)
assert 'chroot "$ROOT" git -C "$CHROOT_SOURCE_REPO" fetch' in native_installer, (
    'chroot git transport must use CHROOT_SOURCE_REPO'
)
