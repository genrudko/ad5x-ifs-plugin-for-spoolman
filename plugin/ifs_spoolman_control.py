#!/usr/bin/env python3
"""Read-only discovery layer for the future AD5X IFS control UI.

This phase deliberately does not execute G-code and does not expose write
endpoints. It reports printer activity, extruder state, active IFS slot,
registered macro candidates, filtered macro definitions and explicit blockers
so the real control contract can be designed from observed Z-Mod capabilities
instead of assumptions.
"""

import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_local as local
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.12-beta"
_BaseHandler = core.Handler

CONTROL_MACRO_CANDIDATES = (
    "gcode_macro LOAD_FILAMENT",
    "gcode_macro UNLOAD_FILAMENT",
    "gcode_macro CHANGE_FILAMENT",
    "gcode_macro M600",
    "gcode_macro IFS_LOAD",
    "gcode_macro IFS_UNLOAD",
    "gcode_macro IFS_CHANGE",
    "gcode_macro SET_CURRENT_PRUTOK",
    "gcode_macro COLOR",
)

RELATED_MACRO_TOKENS = (
    "filament",
    "prutok",
    "ifs",
    "load",
    "unload",
    "change",
    "color",
    "purge",
    "insert",
    "remove",
    "cut",
)


def _moonraker_result(path):
    response = core.http_json(
        core.MOONRAKER + path,
        timeout=max(float(core.HTTP_TIMEOUT), 3.0),
    )
    result = response.get("result", {})
    if not isinstance(result, dict):
        raise RuntimeError("Moonraker вернул неожиданный формат ответа")
    return result


def _registered_objects():
    result = _moonraker_result("/printer/objects/list")
    objects = result.get("objects", [])
    if not isinstance(objects, list):
        raise RuntimeError("Moonraker не вернул список объектов Klipper")
    return sorted(str(item) for item in objects)


def _query_runtime_objects():
    names = {
        "print_stats": "state,filename",
        "extruder": "temperature,target,can_extrude",
        "idle_timeout": "state,printing_time",
        "pause_resume": "is_paused",
    }
    query = "&".join(
        f"{urllib.parse.quote(name)}={urllib.parse.quote(fields)}"
        for name, fields in names.items()
    )
    result = _moonraker_result("/printer/objects/query?" + query)
    status = result.get("status", {})
    return status if isinstance(status, dict) else {}


def _query_configfile_settings():
    result = _moonraker_result("/printer/objects/query?configfile=settings")
    status = result.get("status", {})
    if not isinstance(status, dict):
        raise RuntimeError("Klipper не вернул status объекта configfile")
    configfile = status.get("configfile", {})
    if not isinstance(configfile, dict):
        raise RuntimeError("Klipper не вернул объект configfile")
    settings = configfile.get("settings", {})
    if not isinstance(settings, dict):
        raise RuntimeError("Klipper не вернул configfile.settings")
    return settings


def _active_slot_snapshot():
    snapshot = core.state_snapshot()
    slot = snapshot.get("confirmed_active_slot")
    if slot is None:
        slot = snapshot.get("active_slot")
    try:
        return int(slot) if slot is not None else None
    except (TypeError, ValueError):
        return None


def _is_related_macro(name):
    lowered = str(name).lower()
    return lowered.startswith("gcode_macro ") and any(
        token in lowered for token in RELATED_MACRO_TOKENS
    )


def _macro_report(objects):
    object_set = set(objects)
    found = [name for name in CONTROL_MACRO_CANDIDATES if name in object_set]
    related = [name for name in objects if _is_related_macro(name)]
    return {
        "known_candidates": list(CONTROL_MACRO_CANDIDATES),
        "found_candidates": found,
        "related_registered_macros": related,
        "required_contract_selected": False,
    }


def _normalize_macro_section(name, raw):
    if not isinstance(raw, dict):
        return {
            "name": name,
            "available": True,
            "settings": {},
            "gcode": None,
        }

    gcode = raw.get("gcode")
    if gcode is not None:
        gcode = str(gcode)

    settings = {}
    for key, value in raw.items():
        if key == "gcode":
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            settings[str(key)] = value
        else:
            settings[str(key)] = str(value)

    return {
        "name": name,
        "available": True,
        "settings": settings,
        "gcode": gcode,
    }


def macro_contract_discovery():
    checked_at = core.timestamp_now()
    objects = _registered_objects()
    settings = _query_configfile_settings()

    registered = [name for name in objects if _is_related_macro(name)]
    candidate_names = sorted(set(CONTROL_MACRO_CANDIDATES).union(registered))
    definitions = []
    missing = []

    for object_name in candidate_names:
        section_name = object_name.lower()
        raw = settings.get(section_name)
        if raw is None:
            raw = settings.get(object_name)
        if raw is None:
            missing.append(object_name)
            continue
        definitions.append(_normalize_macro_section(object_name, raw))

    return {
        "phase": "macro-contract-discovery",
        "version": RUNTIME_VERSION,
        "checked_at": checked_at,
        "read_only": True,
        "control_enabled": False,
        "write_endpoints_enabled": False,
        "gcode_executed": False,
        "candidate_count": len(candidate_names),
        "definition_count": len(definitions),
        "registered_related_macros": registered,
        "definitions": definitions,
        "missing_from_configfile_settings": missing,
        "contract_selected": False,
        "note": (
            "Определения получены только для анализа. Ни один макрос не выполнен."
        ),
    }


def control_readiness():
    checked_at = core.timestamp_now()
    blockers = []
    warnings = []
    errors = []
    objects = []
    runtime_status = {}

    try:
        objects = _registered_objects()
        runtime_status = _query_runtime_objects()
        moonraker_available = True
    except Exception as exc:
        moonraker_available = False
        errors.append(str(exc))
        blockers.append({
            "code": "moonraker_unavailable",
            "message": "Moonraker или Klipper недоступен для проверки состояния",
        })

    print_stats = runtime_status.get("print_stats", {})
    if not isinstance(print_stats, dict):
        print_stats = {}
    print_state = str(print_stats.get("state") or "unknown").lower()
    printing = print_state in {"printing", "paused"}
    if printing:
        blockers.append({
            "code": "print_in_progress",
            "message": "Операции с филаментом заблокированы во время печати или паузы",
        })
    elif print_state == "unknown":
        warnings.append({
            "code": "print_state_unknown",
            "message": "Состояние печати не определено",
        })

    extruder = runtime_status.get("extruder", {})
    if not isinstance(extruder, dict):
        extruder = {}
    temperature = extruder.get("temperature")
    target = extruder.get("target")
    can_extrude = extruder.get("can_extrude")
    if temperature is None:
        warnings.append({
            "code": "extruder_temperature_unknown",
            "message": "Температура экструдера не определена",
        })

    active_slot = _active_slot_snapshot()
    if active_slot is None:
        blockers.append({
            "code": "active_slot_unknown",
            "message": "Активный слот IFS не подтверждён",
        })

    cached_local = local._cached_local_inventory()
    if cached_local.get("stale") is True:
        warnings.append({
            "code": "ifs_presence_stale",
            "message": "Физическое состояние слотов IFS устарело",
        })
    if not cached_local.get("presence_cached"):
        warnings.append({
            "code": "ifs_presence_not_cached",
            "message": "Физическое состояние слотов IFS ещё не получено",
        })

    macros = _macro_report(objects)
    if not macros["found_candidates"] and not macros["related_registered_macros"]:
        blockers.append({
            "code": "control_macro_contract_unknown",
            "message": "Не обнаружены подтверждённые макросы загрузки или выгрузки IFS",
        })
    else:
        warnings.append({
            "code": "control_macro_contract_unverified",
            "message": "Макросы обнаружены, но их параметры и побочные эффекты ещё не подтверждены",
        })

    return {
        "phase": "readiness-discovery",
        "version": RUNTIME_VERSION,
        "checked_at": checked_at,
        "read_only": True,
        "control_enabled": False,
        "write_endpoints_enabled": False,
        "gcode_executed": False,
        "ready_for_commands": False,
        "moonraker_available": moonraker_available,
        "macro_contract_endpoint": "/api/ifs/control/macro-contract",
        "printer": {
            "state": print_state,
            "printing_or_paused": printing,
            "filename": print_stats.get("filename"),
            "idle_timeout": runtime_status.get("idle_timeout", {}),
            "pause_resume": runtime_status.get("pause_resume", {}),
        },
        "extruder": {
            "temperature": temperature,
            "target": target,
            "can_extrude": can_extrude,
        },
        "ifs": {
            "active_slot": active_slot,
            "local_available": cached_local.get("available") is True,
            "presence_cached": cached_local.get("presence_cached") is True,
            "presence_stale": cached_local.get("stale") is True,
            "slots": cached_local.get("slots", {}),
        },
        "macros": macros,
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
    }


class ControlRuntimeHandler(_BaseHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in {
            "/api/ifs/control/readiness",
            "/api/ifs/control/capabilities",
        }:
            try:
                self.send_json(200, control_readiness())
            except Exception as exc:
                self.send_json(500, {
                    "phase": "readiness-discovery",
                    "read_only": True,
                    "control_enabled": False,
                    "write_endpoints_enabled": False,
                    "gcode_executed": False,
                    "ready_for_commands": False,
                    "error": str(exc),
                })
            return
        if path == "/api/ifs/control/macro-contract":
            try:
                self.send_json(200, macro_contract_discovery())
            except Exception as exc:
                self.send_json(500, {
                    "phase": "macro-contract-discovery",
                    "read_only": True,
                    "control_enabled": False,
                    "write_endpoints_enabled": False,
                    "gcode_executed": False,
                    "contract_selected": False,
                    "error": str(exc),
                })
            return
        super().do_GET()


runtime.RUNTIME_VERSION = RUNTIME_VERSION
local.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = ControlRuntimeHandler


if __name__ == "__main__":
    core.main()
