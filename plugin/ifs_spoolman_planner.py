#!/usr/bin/env python3
"""Validated, read-only operation planner for AD5X IFS control.

This layer selects the observed Z-Mod macro contract and builds deterministic
operation plans. It never sends G-code and exposes no write endpoint.
"""

import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_control as control
import ifs_spoolman_local as local
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.13-beta"
_BaseHandler = core.Handler

CONTRACT = {
    "load_or_switch": {
        "macro": "_INSERT_PRUTOK_IFS",
        "required_parameters": ["PRUTOK", "FILAMENT_TYPE", "TEMP"],
        "fixed_parameters": {"NEED_STOP": 1, "TRASH": 0},
        "effects": [
            "homes axes through _G28",
            "removes currently loaded filament",
            "moves toolhead to the waste area",
            "heats the extruder",
            "feeds filament through IFS and extruder",
            "purges and cleans the nozzle",
            "sets the active extruder slot",
            "stops extruder heating when NEED_STOP=1",
        ],
    },
    "unload": {
        "macro": "_REMOVE_PRUTOK_IFS",
        "required_parameters": ["PRUTOK", "FILAMENT_TYPE", "TEMP"],
        "fixed_parameters": {"NEED_STOP": 1},
        "effects": [
            "homes axes through _G28",
            "moves toolhead to the waste area",
            "heats the extruder",
            "cuts and retracts filament",
            "returns filament through IFS",
            "stops extruder heating when NEED_STOP=1",
        ],
    },
}

MATERIAL_TEMPERATURES = {
    "PLA": 210,
    "PETG": 240,
    "ABS": 250,
    "ASA": 250,
    "TPU": 220,
}


def _normalize_slot(value):
    try:
        slot = int(value)
    except (TypeError, ValueError):
        raise ValueError("slot должен быть целым числом от 1 до 4")
    if not 1 <= slot <= int(core.SLOT_COUNT):
        raise ValueError(f"slot должен быть в диапазоне 1–{core.SLOT_COUNT}")
    return slot


def _normalize_material(value):
    material = str(value or "").strip().upper()
    return material or "PLA"


def _temperature_for(material, override):
    if override not in (None, ""):
        try:
            temperature = int(float(override))
        except (TypeError, ValueError):
            raise ValueError("temperature должен быть числом")
        if not 170 <= temperature <= 300:
            raise ValueError("temperature должен быть в диапазоне 170–300 °C")
        return temperature, "request"
    return MATERIAL_TEMPERATURES.get(material, 220), (
        "material_profile" if material in MATERIAL_TEMPERATURES else "fallback"
    )


def _macro_names():
    try:
        settings = control._query_configfile_settings()
    except Exception:
        return set()
    return {str(name).lower() for name in settings}


def _runtime_snapshot():
    readiness = control.control_readiness()
    cached = local._cached_local_inventory()
    return readiness, cached


def _slot_data(cached, slot):
    return dict(cached.get("slots", {}).get(str(slot), {}) or {})


def _command(macro, parameters):
    parts = [macro]
    for key, value in parameters.items():
        text = str(value).replace("\n", " ").replace("\r", " ").strip()
        if " " in text:
            text = '"' + text.replace('"', "") + '"'
        parts.append(f"{key}={text}")
    return " ".join(parts)


def operation_plan(action, slot=None, material=None, temperature=None):
    action = str(action or "").strip().lower()
    aliases = {"load": "load", "switch": "switch", "change": "switch", "unload": "unload"}
    if action not in aliases:
        raise ValueError("action должен быть load, switch или unload")
    action = aliases[action]

    readiness, cached = _runtime_snapshot()
    blockers = list(readiness.get("blockers", []))
    warnings = list(readiness.get("warnings", []))
    active_slot = readiness.get("ifs", {}).get("active_slot")

    if action == "unload":
        target_slot = _normalize_slot(slot if slot not in (None, "") else active_slot)
        contract_name = "unload"
    else:
        target_slot = _normalize_slot(slot)
        contract_name = "load_or_switch"

    target = _slot_data(cached, target_slot)
    target_material = _normalize_material(material or target.get("material"))
    target_temperature, temperature_source = _temperature_for(target_material, temperature)
    filament_present = target.get("filament_present")

    if action in {"load", "switch"} and filament_present is not True:
        blockers.append({
            "code": "target_slot_empty",
            "message": f"В слоте IFS {target_slot} не подтверждено наличие филамента",
        })
    if action == "load" and active_slot == target_slot:
        warnings.append({
            "code": "slot_already_active",
            "message": f"Слот IFS {target_slot} уже активен; операция фактически будет повторной загрузкой",
        })
    if action == "switch" and active_slot == target_slot:
        blockers.append({
            "code": "target_slot_already_active",
            "message": f"Слот IFS {target_slot} уже активен",
        })
    if action == "unload" and active_slot != target_slot:
        blockers.append({
            "code": "unload_slot_not_active",
            "message": "Выгружать разрешено только подтверждённый активный слот",
        })
    if action == "unload" and filament_present is not True:
        warnings.append({
            "code": "active_slot_presence_not_confirmed",
            "message": "Наличие филамента в активном слоте не подтверждено",
        })

    contract = CONTRACT[contract_name]
    macro = contract["macro"]
    if f"gcode_macro {macro}".lower() not in _macro_names():
        blockers.append({
            "code": "selected_macro_missing",
            "message": f"Подтверждённый макрос {macro} отсутствует в configfile.settings",
        })

    parameters = {
        "PRUTOK": target_slot,
        "FILAMENT_TYPE": target_material,
        "TEMP": target_temperature,
        **contract["fixed_parameters"],
    }

    return {
        "phase": "operation-planning",
        "version": RUNTIME_VERSION,
        "checked_at": core.timestamp_now(),
        "read_only": True,
        "control_enabled": False,
        "write_endpoints_enabled": False,
        "gcode_executed": False,
        "contract_selected": True,
        "plan_executable": not blockers,
        "action": action,
        "active_slot": active_slot,
        "target_slot": target_slot,
        "target_slot_state": target,
        "material": target_material,
        "temperature": target_temperature,
        "temperature_source": temperature_source,
        "selected_contract": contract_name,
        "macro": macro,
        "parameters": parameters,
        "gcode_preview": _command(macro, parameters),
        "side_effects": contract["effects"],
        "blockers": blockers,
        "warnings": warnings,
        "execution": {
            "available": False,
            "reason": "Патч формирует только план и не выполняет G-code",
        },
    }


def contract_summary():
    names = _macro_names()
    selected = {}
    for operation, contract in CONTRACT.items():
        macro = contract["macro"]
        selected[operation] = {
            **contract,
            "available": f"gcode_macro {macro}".lower() in names,
        }
    return {
        "phase": "validated-contract",
        "version": RUNTIME_VERSION,
        "checked_at": core.timestamp_now(),
        "read_only": True,
        "control_enabled": False,
        "write_endpoints_enabled": False,
        "gcode_executed": False,
        "contract_selected": True,
        "selected": selected,
        "rejected_as_ifs_control": {
            "LOAD_FILAMENT": "двигает только экструдер и не выбирает слот IFS",
            "UNLOAD_FILAMENT": "двигает только экструдер и не возвращает нить через IFS",
            "CHANGE_FILAMENT": "только отправляет RESPOND T{channel}; реальная семантика зависит от внешнего обработчика",
            "M600": "интерактивная пауза для печати, не самостоятельное управление IFS",
        },
        "temperature_profiles": MATERIAL_TEMPERATURES,
    }


class PlannerRuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/api/ifs/control/contract":
            try:
                self.send_json(200, contract_summary())
            except Exception as exc:
                self.send_json(500, {"error": str(exc), "gcode_executed": False})
            return
        if path == "/api/ifs/control/plan":
            try:
                self.send_json(200, operation_plan(
                    action=query.get("action", [""])[0],
                    slot=query.get("slot", [None])[0],
                    material=query.get("material", [None])[0],
                    temperature=query.get("temperature", [None])[0],
                ))
            except ValueError as exc:
                self.send_json(400, {"error": str(exc), "gcode_executed": False})
            except Exception as exc:
                self.send_json(500, {"error": str(exc), "gcode_executed": False})
            return
        super().do_GET()


runtime.RUNTIME_VERSION = RUNTIME_VERSION
local.RUNTIME_VERSION = RUNTIME_VERSION
control.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = PlannerRuntimeHandler


if __name__ == "__main__":
    core.main()
