from pathlib import Path
import re

workflow = Path(".github/workflows/native-fluidd.yml").read_text()

match = re.search(
    r"on:\n  push:\n    branches:\n(?P<branches>(?:      - [^\n]+\n)+)",
    workflow,
)
assert match, "native Fluidd push branch list not found"
branches = {line.strip()[2:] for line in match.group("branches").splitlines()}
assert "release/standalone-0.6.x" in branches, (
    "native Fluidd compatibility workflow must run for standalone release pushes"
)

assert re.search(
    r"EVENT_NAME.*push.*REF_NAME.*main.*REF_NAME.*release/standalone-0\.6\.x",
    workflow,
    re.S,
), "standalone release pushes must request compatibility publication"
