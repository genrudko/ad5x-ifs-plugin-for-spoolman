import ast
from pathlib import Path
import urllib.parse

BACKEND = Path("plugin/ifs_spoolman.py")
CARD = Path("native-fluidd/overlay/src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue")
LEGACY_CARD = Path("plugin/ifs-spoolman-card.js")

backend_source = BACKEND.read_text(encoding="utf-8")
card_source = CARD.read_text(encoding="utf-8")
legacy_card_source = LEGACY_CARD.read_text(encoding="utf-8")


def load_backend_function(name):
    tree = ast.parse(backend_source)
    node = next(
        (item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name),
        None,
    )
    if node is None:
        raise AssertionError(f"backend helper {name} is missing")
    module = ast.Module(body=[node], type_ignores=[])
    namespace = {"urllib": urllib}
    exec(compile(module, str(BACKEND), "exec"), namespace)
    return namespace[name]


normalize_spoolman_web_url = load_backend_function("normalize_spoolman_web_url")

assert normalize_spoolman_web_url("http://151.242.17.56:7912") == "http://151.242.17.56:7912"
assert normalize_spoolman_web_url("https://spool.example.test/") == "https://spool.example.test"
assert normalize_spoolman_web_url("ftp://spool.example.test") is None
assert normalize_spoolman_web_url("http://user:secret@spool.example.test") is None
assert normalize_spoolman_web_url("") is None

assert 'MOONRAKER + "/server/config"' in backend_source
assert '"spoolman_url"' in backend_source

assert 'coaxial: "Коэкструзия"' in backend_source
assert 'coaxial: "Коэкструзия"' in legacy_card_source
assert 'Коаксиальный' not in backend_source
assert 'Коаксиальный' not in legacy_card_source

assert '/api/config' in card_source
assert 'openSpoolman' in card_source
assert 'Spoolman ↗' in card_source
assert 'collapsedSpool' in card_source
assert 'ifs-collapsed-progress__value' in card_source
assert 'background: spoolGradient(collapsedSpool)' in card_source
assert 'percentage(collapsedSpool)' in card_source
assert ':color="connected ? \'success\' : \'warning\'"' not in card_source.split('<template #collapsed-content>', 1)[1]
