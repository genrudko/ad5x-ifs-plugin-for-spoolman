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
