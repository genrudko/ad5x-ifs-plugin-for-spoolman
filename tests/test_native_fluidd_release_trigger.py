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

assert "- cron: '17 3 * * *'" in workflow, (
    "native Fluidd upstream polling must run once per day"
)
assert "- cron: '17,47 * * * *'" not in workflow

assert "gh api \"repos/${UPSTREAM_REPO}/releases/latest\" --jq '.tag_name'" in workflow, (
    "upstream release lookup must use authenticated GitHub API access"
)
assert "native-fluidd/release-state.json" in workflow
assert "Resolve plugin release state" in workflow
assert "git push --atomic origin HEAD:\"$RELEASE_BRANCH\" \"refs/tags/$NEW_TAG\"" in workflow
assert "gh release create \"$NEW_TAG\"" in workflow

assert "github.event_name == 'workflow_dispatch' && inputs.publish == true" in workflow, (
    "manual publish runs must be allowed to execute the plugin release path"
)
assert "release/standalone-0.6.x" in workflow, (
    "scheduled/manual publish runs must use the standalone release line as source"
)

assert "grep -Fq 'pnpm run type-check' .github/workflows/_build.yml" in workflow, (
    "native Fluidd CI must follow the exact upstream release's type-check policy"
)
assert "Upstream build policy omits type-check" in workflow, (
    "upstream releases that intentionally omit the broken global type-check must not be blocked"
)
assert "pnpm run lint --no-fix" in workflow
assert "pnpm run test:unit" in workflow
assert "pnpm run circular-check" in workflow
assert "github.event_name == 'push' && github.ref_name == 'release/standalone-0.6.x'" in workflow, (
    "a production release-line compatibility repair must be able to publish the resulting plugin release immediately"
)

