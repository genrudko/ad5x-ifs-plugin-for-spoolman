from pathlib import Path
import ast
import urllib.parse

root = Path(__file__).resolve().parents[1]
source = (root / "plugin/ifs_spoolman.py").read_text(encoding="utf-8")
vue = (root / "native-fluidd/overlay/src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue").read_text(encoding="utf-8")

# Polling must not destroy an open native select.
assert "let slotsRenderPending = false;" in source
assert "function slotSelectIsActive()" in source
assert "function renderSlotsPreservingInteraction()" in source
assert "select.addEventListener(\"blur\"" in source
assert "renderSlotsPreservingInteraction();" in source

# Web settings must expose and persist only the Spoolman web URL.
assert 'id="spoolmanUrlInput"' in source
assert 'id="saveConfigButton"' in source
assert 'if self.path=="/api/config":' in source
assert '"spoolman_url": None' in source
assert '"spoolman_url_override": CONFIG["spoolman_url"]' in source
assert "def update_public_config(raw):" in source

# Validate the real config normalization code without importing the daemon.
tree = ast.parse(source)
wanted_assignments = {"CONFIG_SCHEMA_VERSION", "DEFAULT_CONFIG", "CONFIG_KEYS"}
wanted_functions = {"normalize_spoolman_web_url", "validate_config"}
nodes = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if names & wanted_assignments:
            nodes.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
        nodes.append(node)
namespace = {"urllib": __import__("urllib"), "os": __import__("os")}
namespace["urllib"].parse = urllib.parse
exec(compile(ast.Module(body=nodes, type_ignores=[]), "config_subset", "exec"), namespace)
cfg = dict(namespace["DEFAULT_CONFIG"])
cfg["spoolman_url"] = "192.168.1.50:7912/"
validated = namespace["validate_config"](cfg)
assert validated["spoolman_url"] == "http://192.168.1.50:7912"
cfg["spoolman_url"] = "ftp://192.168.1.50"
try:
    namespace["validate_config"](cfg)
except ValueError:
    pass
else:
    raise AssertionError("invalid Spoolman URL must be rejected")

# Disabled Spoolman button must remain legible, not disappear into the header.
assert vue.count('class="ifs-spoolman-link"') == 2
assert ".ifs-spoolman-link.v-btn--disabled" in vue
assert "color: inherit !important;" in vue
