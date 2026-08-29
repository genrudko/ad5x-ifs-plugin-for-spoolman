#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugin" / "ifs_spoolman.py"
text = SOURCE.read_text(encoding="utf-8")
tree = ast.parse(text)


def load_function(name):
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"RuntimeError": RuntimeError}
    exec(compile(module, str(SOURCE), "exec"), ns)
    return ns[name]


normalize = load_function("normalize_moonraker_spoolman_status")

assert normalize({"spoolman_connected": True, "spool_id": 19}) == (True, 19)
assert normalize({"spoolman_connected": True, "spool_id": "42"}) == (True, 42)
assert normalize({"spoolman_connected": True, "spool_id": None}) == (True, None)
assert normalize({"spoolman_connected": False, "spool_id": None}) == (False, None)

try:
    normalize({"spoolman_connected": True, "spool_id": "bad"})
except RuntimeError:
    pass
else:
    raise AssertionError("invalid spool_id must fail")


# Behavioral regression for the reported fresh-install case: Spoolman health
# must become online even when no IFS slot has any spool assignment.
selected = {
    "normalize_moonraker_spoolman_status",
    "probe_spoolman_status",
    "refresh_spoolman_health",
}
health_nodes = [
    item for item in tree.body
    if isinstance(item, ast.FunctionDef) and item.name in selected
]
health_module = ast.Module(body=health_nodes, type_ignores=[])
ast.fix_missing_locations(health_module)
health_state = {
    "moonraker_status_ok": False,
    "spoolman_connected": False,
    "moonraker_spool_id": None,
}
health_events = []

def fake_set_state(**values):
    health_state.update(values)

def fake_state_snapshot():
    return dict(health_state)

def fake_get_moonraker_status():
    return {"spoolman_connected": True, "spool_id": None}

def fake_event_log(*args, **kwargs):
    health_events.append((args, kwargs))

health_ns = {
    "RuntimeError": RuntimeError,
    "set_state": fake_set_state,
    "state_snapshot": fake_state_snapshot,
    "get_moonraker_status": fake_get_moonraker_status,
    "event_log": fake_event_log,
}
exec(compile(health_module, str(SOURCE), "exec"), health_ns)
assert health_ns["refresh_spoolman_health"]() is True
assert health_state["moonraker_status_ok"] is True
assert health_state["spoolman_connected"] is True
assert health_state["moonraker_spool_id"] is None
assert health_state["spoolman_probe_error"] is None

assert 'APP_VERSION = "0.5.1-beta"' in text
assert 'PACKAGE_VERSION_FILE = os.path.join(APP_DIR, "VERSION")' in text
assert 'HTML = HTML.replace("__APP_VERSION__", APP_VERSION)' in text
assert 'server_version="IFS-Spoolman/0.5.1-beta"' in text
assert 'Handler.server_version = f"IFS-Spoolman/{APP_VERSION}"' in text
assert 'def refresh_spoolman_health():' in text
assert 'health_probe_interval = max(2.0, min(10.0, POLL_INTERVAL * 5.0))' in text

# Critical regression: health probing must occur in monitor independently and
# before slot-assignment synchronization can early-return on desired is None.
monitor = text.index('def monitor():')
probe = text.index('refresh_spoolman_health()', monitor)
assignment_guard = text.index('if desired is None:')
assert probe > monitor
assert assignment_guard < monitor, "assignment guard belongs to synchronize, not health"

assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "0.6.6-beta"

print("release logic checks: OK")
