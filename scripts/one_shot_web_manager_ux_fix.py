#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path.cwd()


def run(*args, check=True, capture=False):
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=capture,
    )
    if check and result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return result


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


# ---- RED: write regression tests before touching production code ----
web_test = ROOT / "tests/test_web_manager_ux.py"
web_test.write_text(r'''from pathlib import Path
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
''', encoding="utf-8")

native_test = ROOT / "tests/test_native_patch_revision.py"
native_text = native_test.read_text(encoding="utf-8")
old_expect = "assert config['patch_revision'] == 9, f\"expected native patch revision 9, got {config['patch_revision']}\""
new_expect = "assert config['patch_revision'] == 10, f\"expected native patch revision 10, got {config['patch_revision']}\""
if old_expect not in native_text:
    raise SystemExit("native revision test baseline is not revision 9")
native_test.write_text(native_text.replace(old_expect, new_expect, 1), encoding="utf-8")

web_red = run("python3", "tests/test_web_manager_ux.py", check=False, capture=True)
native_red = run("python3", "tests/test_native_patch_revision.py", check=False, capture=True)
print(web_red.stdout + web_red.stderr)
print(native_red.stdout + native_red.stderr)
if web_red.returncode == 0 or native_red.returncode == 0:
    raise SystemExit(f"RED not proven: web={web_red.returncode} native={native_red.returncode}")
print(f"RED_CONFIRMED web={web_red.returncode} native={native_red.returncode}")


# ---- GREEN: minimal production changes ----
p = ROOT / "plugin/ifs_spoolman.py"
text = p.read_text(encoding="utf-8")

text = replace_once(
    text,
    '    "moonraker_url": "http://127.0.0.1:7125",\n',
    '    "moonraker_url": "http://127.0.0.1:7125",\n    "spoolman_url": None,\n',
    "default spoolman_url",
)

validation_marker = '    listen_host = result["listen_host"]\n'
validation_block = '''    spoolman_url_raw = result["spoolman_url"]

    if spoolman_url_raw is None or (
        isinstance(spoolman_url_raw, str) and not spoolman_url_raw.strip()
    ):
        spoolman_url = None
    elif not isinstance(spoolman_url_raw, str):
        raise ValueError(
            "config.json: spoolman_url должен быть строкой или null"
        )
    else:
        spoolman_url = normalize_spoolman_web_url(spoolman_url_raw)
        if spoolman_url is None:
            raise ValueError(
                "config.json: spoolman_url должен быть корректным HTTP/HTTPS URL "
                "без учётных данных, query и fragment"
            )

'''
text = replace_once(text, validation_marker, validation_block + validation_marker, "config validation")
text = replace_once(
    text,
    '        "moonraker_url": moonraker_url,\n',
    '        "moonraker_url": moonraker_url,\n        "spoolman_url": spoolman_url,\n',
    "validated config result",
)
text = replace_once(text, 'def get_spoolman_web_url():', 'def get_moonraker_spoolman_web_url():', "moonraker fallback rename")

public_marker = '\n\ndef public_config():\n'
web_url_wrapper = '''

def get_spoolman_web_url():
    configured = CONFIG.get("spoolman_url")
    if configured:
        return configured
    return get_moonraker_spoolman_web_url()
'''
text = replace_once(text, public_marker, web_url_wrapper + public_marker, "effective spoolman url")
text = replace_once(
    text,
    '        "spoolman_url": get_spoolman_web_url(),\n',
    '        "spoolman_url": get_spoolman_web_url(),\n        "spoolman_url_override": CONFIG["spoolman_url"],\n',
    "public config override",
)

config_load_marker = '\n\nCONFIG = load_config()\n'
update_config = '''

def update_public_config(raw):
    if not isinstance(raw, dict):
        raise ValueError("Настройки должны быть JSON-объектом")

    unknown = sorted(set(raw) - {"spoolman_url"})
    if unknown:
        raise ValueError(
            "Через веб-интерфейс нельзя менять параметры: " + ", ".join(unknown)
        )
    if "spoolman_url" not in raw:
        raise ValueError("Не указан параметр spoolman_url")

    candidate = dict(CONFIG)
    candidate["spoolman_url"] = raw.get("spoolman_url")
    validated = validate_config(candidate)

    with lock:
        atomic_write_json(CONFIG_FILE, validated)
        CONFIG.clear()
        CONFIG.update(validated)

    return public_config()
'''
text = replace_once(text, config_load_marker, update_config + config_load_marker, "web config update")

settings_css = '''.settings {
  margin-top: 18px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  overflow: hidden;
}

.settings summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 16px;
  cursor: pointer;
  color: var(--muted);
  font-size: 13px;
  font-weight: 800;
  list-style: none;
}

.settings summary::-webkit-details-marker {
  display: none;
}

.settings-body {
  padding: 0 16px 16px;
}

.settings-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.settings-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 11px;
  outline: none;
  background: var(--surface2);
  color: var(--text);
}

.settings-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .15);
}

.settings-hint {
  margin-top: 9px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}

'''
text = replace_once(text, '.diagnostics {\n', settings_css + '.diagnostics {\n', "settings css")

settings_html = '''  <main class="slots-grid" id="slotsGrid"></main>

  <details class="settings" id="settingsPanel">
    <summary>
      <span>Настройки</span>
      <span>Spoolman</span>
    </summary>

    <div class="settings-body">
      <label class="field-label" for="spoolmanUrlInput">
        Адрес веб-интерфейса Spoolman
      </label>
      <div class="settings-row">
        <input
          class="settings-input"
          id="spoolmanUrlInput"
          type="text"
          inputmode="url"
          autocomplete="url"
          placeholder="http://192.168.1.50:7912"
        >
        <button class="btn btn-primary" id="saveConfigButton" type="button">
          Сохранить
        </button>
      </div>
      <div class="settings-hint" id="spoolmanUrlEffective">
        Если поле пустое, адрес берётся из конфигурации Moonraker.
      </div>
    </div>
  </details>

  <details class="diagnostics">
'''
text = replace_once(
    text,
    '  <main class="slots-grid" id="slotsGrid"></main>\n\n  <details class="diagnostics">\n',
    settings_html,
    "settings markup",
)

text = replace_once(
    text,
    'let requestInProgress = false;\n',
    'let requestInProgress = false;\nlet configData = null;\nlet slotsRenderPending = false;\n',
    "web state",
)

start = text.index('function renderSlots() {')
end = text.index('\nfunction renderSummary()', start)
render_block = text[start:end]
old_tail = '''      renderAll();
    });
  });
}
'''
new_tail = '''      renderAll();
    });

    select.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!slotSelectIsActive()) {
          flushPendingSlotsRender();
        }
      }, 0);
    });
  });
}

function slotSelectIsActive() {
  const active = document.activeElement;
  return Boolean(
    active &&
    active.classList &&
    active.classList.contains("slot-select")
  );
}

function renderSlotsPreservingInteraction() {
  if (slotSelectIsActive()) {
    slotsRenderPending = true;
    return;
  }

  slotsRenderPending = false;
  renderSlots();
}

function flushPendingSlotsRender() {
  if (!slotsRenderPending || slotSelectIsActive()) {
    return;
  }

  slotsRenderPending = false;
  renderSlots();
}
'''
render_block = replace_once(render_block, old_tail, new_tail, "select interaction")
text = text[:start] + render_block + text[end:]

old_render_all = '''function renderAll() {
  renderSummary();
  renderConnection();
  renderSlots();
  renderDiagnostics();
  renderSearchCount();
  renderChangeState();
}
'''
new_render_all = '''function renderAll() {
  renderSummary();
  renderConnection();
  renderSlotsPreservingInteraction();
  renderDiagnostics();
  renderSearchCount();
  renderChangeState();
}
'''
text = replace_once(text, old_render_all, new_render_all, "safe renderAll")

settings_js = '''
function renderWebSettings() {
  if (!configData) {
    return;
  }

  const input = el("spoolmanUrlInput");
  if (document.activeElement !== input) {
    input.value = configData.spoolman_url_override || "";
  }

  el("spoolmanUrlEffective").textContent = configData.spoolman_url
    ? `Используется: ${configData.spoolman_url}`
    : "Адрес не определён. Укажи URL Spoolman и сохрани настройки.";
}

async function loadWebSettings() {
  try {
    configData = await api("/api/config");
    renderWebSettings();
  } catch (error) {
    el("spoolmanUrlEffective").textContent =
      `Не удалось загрузить настройки: ${error instanceof Error ? error.message : String(error)}`;
  }
}

async function saveWebSettings() {
  const value = el("spoolmanUrlInput").value.trim();
  setLoading(true, "Сохранение настроек…");

  try {
    configData = await api("/api/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        spoolman_url: value || null
      })
    });
    renderWebSettings();
    showToast(
      "success",
      "Настройки сохранены",
      configData.spoolman_url
        ? `Spoolman: ${configData.spoolman_url}`
        : "Используется автоматическое определение через Moonraker"
    );
  } catch (error) {
    showToast(
      "error",
      "Ошибка настроек",
      error instanceof Error ? error.message : String(error)
    );
  } finally {
    setLoading(false);
  }
}
'''
text = replace_once(text, '\nasync function loadData({\n', settings_js + '\nasync function loadData({\n', "settings js")
text = replace_once(
    text,
    'el("saveButton").addEventListener("click", saveAssignments);\n',
    'el("saveConfigButton").addEventListener("click", saveWebSettings);\nel("saveButton").addEventListener("click", saveAssignments);\n',
    "settings listener",
)
text = replace_once(
    text,
    'loadData({\n  showLoader: true\n});\n',
    'void loadWebSettings();\n\nloadData({\n  showLoader: true\n});\n',
    "initial settings load",
)
config_post = '''            if self.path=="/api/config":
                body=self.read_json()
                self.send_json(200,update_public_config(body))
                return
'''
text = replace_once(text, '            if self.path=="/api/assign":\n', config_post + '            if self.path=="/api/assign":\n', "config POST endpoint")
p.write_text(text, encoding="utf-8")

vue_path = ROOT / 'native-fluidd/overlay/src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue'
vue = vue_path.read_text(encoding="utf-8")
needle = '            outlined\n            :disabled="!spoolmanUrl"\n'
if vue.count(needle) != 2:
    raise SystemExit(f"spoolman button baseline count={vue.count(needle)}")
vue = vue.replace(needle, '            outlined\n            class="ifs-spoolman-link"\n            :disabled="!spoolmanUrl"\n', 2)
style_marker = '''.ifs-header-actions--mobile {
  display: none;
}
'''
style_add = style_marker + '''
.ifs-spoolman-link.v-btn--disabled {
  color: inherit !important;
  border-color: currentColor !important;
  opacity: .62 !important;
}
'''
vue = replace_once(vue, style_marker, style_add, "disabled Spoolman contrast")
vue_path.write_text(vue, encoding="utf-8")

cfg_path = ROOT / 'native-fluidd/config.json'
cfg = cfg_path.read_text(encoding="utf-8")
cfg = replace_once(cfg, '"patch_revision": 9', '"patch_revision": 10', "native patch revision")
cfg_path.write_text(cfg, encoding="utf-8")

start_path = ROOT / 'scripts/start.sh'
start_text = start_path.read_text(encoding="utf-8")
start_text = replace_once(start_text, 'NATIVE_PATCH_REVISION="9"', 'NATIVE_PATCH_REVISION="10"', "runtime native revision")
start_path.write_text(start_text, encoding="utf-8")

# ---- GREEN verification ----
run("python3", "tests/test_web_manager_ux.py")
run("python3", "tests/test_native_patch_revision.py")
run("python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")
run("python3", "-m", "py_compile", "plugin/ifs_spoolman.py")
run("python3", "-m", "json.tool", "native-fluidd/config.json")
run("python3", "scripts/test_release_logic.py")
for shell in sorted((ROOT / "scripts").glob("*.sh")) + sorted(ROOT.glob("*.sh")):
    run("sh", "-n", str(shell.relative_to(ROOT)))
run("git", "diff", "--check")
print("GREEN_GATE_PASS")

run("git", "add",
    "plugin/ifs_spoolman.py",
    "native-fluidd/overlay/src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue",
    "native-fluidd/config.json",
    "scripts/start.sh",
    "tests/test_native_patch_revision.py",
    "tests/test_web_manager_ux.py")
run("git", "diff", "--cached", "--check")
run("git", "commit", "-m", "fix: preserve web manager interaction and settings")
run("git", "push", "origin", "HEAD:release/standalone-0.6.x")
print("PUSH_COMPLETE")
