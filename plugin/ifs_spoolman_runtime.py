#!/usr/bin/env python3
"""Runtime extension for read-only Z-Mod IFS discovery and status.

This module deliberately exposes no filament movement commands. It imports the
existing backend, augments its health response, adds read-only capability and
IFS status endpoints, and then starts the original monitor and HTTP server.
"""

import json
import threading
import time
import urllib.parse
import urllib.request

import ifs_spoolman as core


RUNTIME_VERSION = "0.8.0-beta"
CAPABILITY_CACHE_SECONDS = 5.0
IFS_STATUS_CACHE_SECONDS = 1.0
IFS_STATUS_GCODE_COUNT = 100
IFS_READY_STATE = 5

COMMAND_CANDIDATES = {
    "insert": ("INSERT_PRUTOK_IFS",),
    "remove": ("REMOVE_PRUTOK_IFS",),
    "remove_current": ("IFS_REMOVE_CURRENT_PRUTOK",),
    "set_extruder_slot": ("SET_EXTRUDER_SLOT",),
    "set_current_filament": ("SET_CURRENT_PRUTOK",),
    "purge": ("PURGE_PRUTOK_IFS",),
    "autoinsert": ("IFS_AUTOINSERT",),
    "status": ("IFS_STATUS",),
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

_ifs_status_lock = threading.RLock()
_ifs_status_cache = {
    "created_monotonic": 0.0,
    "payload": None,
}


def _moonraker_result(path):
    response = core.http_json(core.MOONRAKER + path)
    result = response.get("result", {})
    if not isinstance(result, dict):
        raise RuntimeError("Moonraker вернул неожиданный формат ответа")
    return result


def _moonraker_post(path, payload):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        core.MOONRAKER + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=core.HTTP_TIMEOUT) as response:
        data = json.load(response)
    if data.get("result") != "ok":
        raise RuntimeError("Moonraker не подтвердил выполнение команды")


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


def _registered_commands():
    result = _moonraker_result("/printer/gcode/help")
    return {str(name).strip().upper() for name in result}


def _select_commands(registered):
    selected = {}
    available = {}
    for capability, candidates in COMMAND_CANDIDATES.items():
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


def _normalize_ifs_values(values):
    ports = values.get("Ports", [])
    if not isinstance(ports, list):
        ports = []
    ports = [bool(value) for value in ports]

    stall_mask = values.get("stall_state", 0)
    try:
        stall_mask = int(stall_mask)
    except (TypeError, ValueError):
        stall_mask = 0

    slot_count = max(len(ports), int(getattr(core, "SLOT_COUNT", 4)))
    slot_states = []
    for index in range(slot_count):
        slot_states.append({
            "slot": index + 1,
            "filament_present": ports[index] if index < len(ports) else False,
            "stall": bool((stall_mask >> index) & 1),
        })

    state_code = values.get("State")
    try:
        state_code = int(state_code)
    except (TypeError, ValueError):
        state_code = None

    controller_channel = values.get("Chan")
    pending_insert_slot = values.get("Insert")
    for name, value in (
        ("controller_channel", controller_channel),
        ("pending_insert_slot", pending_insert_slot),
    ):
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = None
        if name == "controller_channel":
            controller_channel = normalized
        else:
            pending_insert_slot = normalized

    with core.lock:
        loaded_extruder_slot = core.state.get("active_slot")

    return {
        "available": True,
        "checked_at": core.timestamp_now(),
        "source": "zmod_ifs_status_gcode",
        "state_code": state_code,
        "ready": state_code == IFS_READY_STATE,
        "controller_channel": controller_channel,
        "loaded_extruder_slot": loaded_extruder_slot,
        "pending_insert_slot": pending_insert_slot or None,
        "need_insert": bool(values.get("NeedInsert", False)),
        "stall": bool(values.get("Stall", False)),
        "stall_mask": stall_mask,
        "slots": slot_states,
        "raw": values,
    }


def _extract_ifs_status(entries, started_at):
    for entry in reversed(entries):
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "response":
            continue
        try:
            entry_time = float(entry.get("time", 0.0))
        except (TypeError, ValueError):
            entry_time = 0.0
        if entry_time + 0.05 < started_at:
            continue

        message = str(entry.get("message", "")).strip()
        if message.startswith("//"):
            message = message[2:].strip()
        if not message.startswith("{"):
            continue

        try:
            values = json.loads(message)
        except json.JSONDecodeError:
            continue

        required = {"State", "Ports", "Silk", "Chan", "Insert"}
        if isinstance(values, dict) and required.issubset(values):
            return values

    raise RuntimeError("Ответ IFS_STATUS не найден в журнале G-code")


def read_ifs_status(force=False):
    now = time.monotonic()
    with _ifs_status_lock:
        cached = _ifs_status_cache["payload"]
        age = now - _ifs_status_cache["created_monotonic"]
        if not force and cached is not None and age < IFS_STATUS_CACHE_SECONDS:
            return dict(cached)

        capabilities = discover_capabilities()
        if not capabilities.get("command_availability", {}).get("status"):
            payload = {
                "available": False,
                "checked_at": core.timestamp_now(),
                "source": None,
                "reason": "ifs_status_command_unavailable",
            }
        elif not capabilities.get("display", {}).get("display_off_confirmed"):
            payload = {
                "available": False,
                "checked_at": core.timestamp_now(),
                "source": None,
                "reason": "zmod_ifs_inactive",
            }
        else:
            try:
                started_at = time.time()
                _moonraker_post(
                    "/printer/gcode/script",
                    {"script": capabilities["commands"]["status"]},
                )
                result = _moonraker_result(
                    "/server/gcode_store?count="
                    + str(IFS_STATUS_GCODE_COUNT)
                )
                entries = result.get("gcode_store", [])
                if not isinstance(entries, list):
                    raise RuntimeError("Moonraker не вернул журнал G-code")
                payload = _normalize_ifs_values(
                    _extract_ifs_status(entries, started_at)
                )
            except Exception as exc:
                payload = {
                    "available": False,
                    "checked_at": core.timestamp_now(),
                    "source": "zmod_ifs_status_gcode",
                    "reason": "ifs_status_probe_failed",
                    "error": str(exc),
                }

        _ifs_status_cache["created_monotonic"] = time.monotonic()
        _ifs_status_cache["payload"] = dict(payload)
        return payload


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
        registered_macros = _registered_macros(objects)
        registered_commands = _registered_commands()
        selected, available = _select_commands(registered_commands)
        printer = _printer_snapshot()

        required_missing = [
            key for key in REQUIRED_CONTROL_KEYS if not available[key]
        ]
        zmod_markers = {
            "zmod_ifs_object": "zmod_ifs" in objects,
            "zmod_color_object": "zmod_color" in objects,
            "ifs_command_family": any(
                name.startswith("IFS_")
                or name.endswith("_PRUTOK_IFS")
                for name in registered_commands
            ),
            "color_macro": "COLOR" in registered_commands,
        }
        zmod_detected = any(zmod_markers.values())

        zmod_ifs_active = (
            zmod_markers["zmod_ifs_object"]
            and available["status"]
            and available["insert"]
            and available["remove"]
        )
        display_off_confirmed = zmod_ifs_active

        blockers = []
        if not zmod_detected:
            blockers.append("zmod_not_detected")
        if required_missing:
            blockers.append("missing_required_commands")
        blockers.append("read_only_phase")
        if not display_off_confirmed:
            blockers.append("native_display_state_not_confirmed")

        payload = {
            "read_only": True,
            "write_actions_enabled": False,
            "checked_at": checked_at,
            "cache_ttl_seconds": CAPABILITY_CACHE_SECONDS,
            "moonraker_reachable": True,
            "zmod_detected": zmod_detected,
            "zmod_markers": zmod_markers,
            "ifs_control_available": (
                zmod_detected
                and not required_missing
                and display_off_confirmed
            ),
            "control_ready": False,
            "control_blockers": blockers,
            "display": {
                "display_off_required": True,
                "display_off_confirmed": display_off_confirmed,
                "state": "off" if display_off_confirmed else "unknown",
                "reason": (
                    "The active zmod_ifs object and its Python-registered "
                    "control commands confirm that native display ownership "
                    "has been released to Klipper."
                    if display_off_confirmed
                    else "The active zmod_ifs command surface was not found."
                ),
            },
            "commands": selected,
            "command_availability": available,
            "required_command_keys": list(REQUIRED_CONTROL_KEYS),
            "missing_required_command_keys": required_missing,
            "registered_command_count": len(registered_commands),
            "registered_macro_count": len(registered_macros),
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
            "commands": {
                key: None for key in COMMAND_CANDIDATES
            },
            "command_availability": {
                key: False for key in COMMAND_CANDIDATES
            },
            "required_command_keys": list(REQUIRED_CONTROL_KEYS),
            "missing_required_command_keys": list(REQUIRED_CONTROL_KEYS),
            "registered_command_count": 0,
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
        "required_commands_present": not bool(
            capabilities.get("missing_required_command_keys")
        ),
        "display_state": capabilities.get("display", {}).get("state"),
        "last_probe_at": capabilities.get("checked_at"),
        "error": capabilities.get("error"),
    }
    return health


class CapabilityHandler(_BaseHandler):
    def do_GET(self):
        split = urllib.parse.urlsplit(self.path)
        path = split.path
        force = urllib.parse.parse_qs(split.query).get(
            "refresh", ["0"]
        )[0].lower() in ("1", "true", "yes")

        if path == "/api/filament/capabilities":
            try:
                self.send_json(200, discover_capabilities(force=force))
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        if path == "/api/filament/ifs-status":
            try:
                payload = read_ifs_status(force=force)
                self.send_json(200 if payload.get("available") else 503, payload)
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return

        super().do_GET()


core.APP_VERSION = RUNTIME_VERSION
core.build_health = build_health_with_capabilities
core.Handler = CapabilityHandler


if __name__ == "__main__":
    core.main()
