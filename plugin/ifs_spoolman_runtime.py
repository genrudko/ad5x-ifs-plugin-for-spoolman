#!/usr/bin/env python3
"""Runtime extension for read-only Z-Mod IFS capability discovery.

This module deliberately exposes no filament movement commands.  It imports the
existing backend, augments its health response, adds a capabilities endpoint,
and then starts the original monitor and HTTP server.
"""

import threading
import time
import urllib.parse

import ifs_spoolman as core


RUNTIME_VERSION = "0.6.0-beta"
CAPABILITY_CACHE_SECONDS = 5.0

MACRO_CANDIDATES = {
    "insert": ("INSERT_PRUTOK_IFS",),
    "remove": ("REMOVE_PRUTOK_IFS",),
    "set_extruder_slot": ("SET_EXTRUDER_SLOT",),
    "set_current_filament": ("SET_CURRENT_PRUTOK",),
    "purge": ("PURGE_PRUTOK_IFS",),
    "stop": ("IFS_F112",),
    "state": ("IFS_F13",),
    "motion": ("IFS_MOTION",),
    "equivalent_filament": ("ANALOG_PRUTOK",),
    "display_off": ("DISPLAY_OFF",),
    "display_on": ("DISPLAY_ON",),
    "color_menu": ("COLOR",),
}

REQUIRED_CONTROL_KEYS = (
    "insert",
    "remove",
    "set_extruder_slot",
    "stop",
)

_cache_lock = threading.RLock()
_cache = {
    "created_monotonic": 0.0,
    "payload": None,
}


def _moonraker_result(path):
    response = core.http_json(core.MOONRAKER + path)
    result = response.get("result", {})
    if not isinstance(result, dict):
        raise RuntimeError("Moonraker вернул неожиданный формат ответа")
    return result


def _registered_objects():
    result = _moonraker_result("/printer/objects/list")
    objects = result.get("objects", [])
    if not isinstance(objects, list):
        raise RuntimeError("Moonraker не вернул список объектов Klipper")
    return [str(item) for item in objects]


def _registered_macros(objects):
    macros = set()
    prefix = "gcode_macro "
    for object_name in objects:
        lowered = object_name.lower()
        if lowered.startswith(prefix):
            macros.add(object_name[len(prefix):].strip().upper())
    return macros


def _select_macros(registered):
    selected = {}
    available = {}
    for capability, candidates in MACRO_CANDIDATES.items():
        match = next((name for name in candidates if name in registered), None)
        selected[capability] = match
        available[capability] = match is not None
    return selected, available


def _printer_snapshot():
    query = urllib.parse.urlencode({
        "print_stats": "",
        "webhooks": "",
        "extruder": "",
    })
    result = _moonraker_result("/printer/objects/query?" + query)
    status = result.get("status", {})
    if not isinstance(status, dict):
        status = {}

    print_stats = status.get("print_stats", {})
    webhooks = status.get("webhooks", {})
    extruder = status.get("extruder", {})

    return {
        "klipper_state": webhooks.get("state"),
        "klipper_state_message": webhooks.get("state_message"),
        "print_state": print_stats.get("state"),
        "filename": print_stats.get("filename"),
        "extruder_temperature": extruder.get("temperature"),
        "extruder_target": extruder.get("target"),
    }


def discover_capabilities(force=False):
    now = time.monotonic()
    with _cache_lock:
        cached = _cache["payload"]
        age = now - _cache["created_monotonic"]
        if not force and cached is not None and age < CAPABILITY_CACHE_SECONDS:
            return dict(cached)

    checked_at = core.timestamp_now()

    try:
        objects = _registered_objects()
        registered = _registered_macros(objects)
        selected, available = _select_macros(registered)
        printer = _printer_snapshot()

        required_missing = [
            key for key in REQUIRED_CONTROL_KEYS if not available[key]
        ]
        zmod_markers = {
            "zmod_ifs_object": "zmod_ifs" in objects,
            "zmod_color_object": "zmod_color" in objects,
            "ifs_macro_family": any(
                name.startswith("IFS_")
                or name.endswith("_PRUTOK_IFS")
                for name in registered
            ),
            "color_macro": "COLOR" in registered,
        }
        zmod_detected = any(zmod_markers.values())
        display_off_required = True
        display_off_confirmed = False

        payload = {
            "read_only": True,
            "write_actions_enabled": False,
            "checked_at": checked_at,
            "cache_ttl_seconds": CAPABILITY_CACHE_SECONDS,
            "moonraker_reachable": True,
            "zmod_detected": zmod_detected,
            "zmod_markers": zmod_markers,
            "ifs_control_available": (
                zmod_detected and not required_missing
            ),
            "control_ready": False,
            "control_blockers": [
                *(["zmod_not_detected"] if not zmod_detected else []),
                *(
                    ["missing_required_macros"]
                    if required_missing
                    else []
                ),
                "read_only_phase",
                "native_display_state_not_confirmed",
            ],
            "display": {
                "display_off_required": display_off_required,
                "display_off_confirmed": display_off_confirmed,
                "state": "unknown",
                "reason": (
                    "Capability discovery does not execute DISPLAY_OFF and "
                    "does not infer display state without a reliable signal."
                ),
            },
            "macros": selected,
            "macro_availability": available,
            "required_macro_keys": list(REQUIRED_CONTROL_KEYS),
            "missing_required_macro_keys": required_missing,
            "registered_macro_count": len(registered),
            "printer": printer,
        }
    except Exception as exc:
        payload = {
            "read_only": True,
            "write_actions_enabled": False,
            "checked_at": checked_at,
            "cache_ttl_seconds": CAPABILITY_CACHE_SECONDS,
            "moonraker_reachable": False,
            "zmod_detected": False,
            "ifs_control_available": False,
            "control_ready": False,
            "control_blockers": [
                "capability_probe_failed",
                "read_only_phase",
            ],
            "display": {
                "display_off_required": True,
                "display_off_confirmed": False,
                "state": "unknown",
            },
            "macros": {
                key: None for key in MACRO_CANDIDATES
            },
            "macro_availability": {
                key: False for key in MACRO_CANDIDATES
            },
            "required_macro_keys": list(REQUIRED_CONTROL_KEYS),
            "missing_required_macro_keys": list(REQUIRED_CONTROL_KEYS),
            "registered_macro_count": 0,
            "printer": {},
            "error": str(exc),
        }

    with _cache_lock:
        _cache["created_monotonic"] = time.monotonic()
        _cache["payload"] = dict(payload)

    return payload


_original_build_health = core.build_health
_BaseHandler = core.Handler


def build_health_with_capabilities():
    health = _original_build_health()
    capabilities = discover_capabilities()
    health.setdefault("components", {})["filament_control"] = {
        "ok": capabilities.get("ifs_control_available", False),
        "read_only": True,
        "write_actions_enabled": False,
        "zmod_detected": capabilities.get("zmod_detected", False),
        "required_macros_present": not bool(
            capabilities.get("missing_required_macro_keys")
        ),
        "display_state": capabilities.get("display", {}).get("state"),
        "last_probe_at": capabilities.get("checked_at"),
        "error": capabilities.get("error"),
    }
    return health


class CapabilityHandler(_BaseHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/filament/capabilities":
            try:
                force = urllib.parse.parse_qs(
                    urllib.parse.urlsplit(self.path).query
                ).get("refresh", ["0"])[0] in ("1", "true", "yes")
                self.send_json(200, discover_capabilities(force=force))
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        super().do_GET()


core.APP_VERSION = RUNTIME_VERSION
core.build_health = build_health_with_capabilities
core.Handler = CapabilityHandler


if __name__ == "__main__":
    core.main()
