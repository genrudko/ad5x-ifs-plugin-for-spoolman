from pathlib import Path
import json
import re

root = Path(__file__).resolve().parents[1]
config = json.loads((root / 'native-fluidd/config.json').read_text())
start = (root / 'scripts/start.sh').read_text()
match = re.search(r'^NATIVE_PATCH_REVISION="(\d+)"$', start, re.M)
assert match, 'NATIVE_PATCH_REVISION missing from scripts/start.sh'
assert config['patch_revision'] == 9, f"expected native patch revision 9, got {config['patch_revision']}"
assert int(match.group(1)) == config['patch_revision'], (
    f"scripts/start.sh revision {match.group(1)} != native-fluidd/config.json {config['patch_revision']}"
)
