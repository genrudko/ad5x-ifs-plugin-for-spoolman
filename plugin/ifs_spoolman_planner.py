#!/usr/bin/env python3
"""Validated planner and guarded two-step executor for AD5X IFS control.

GET endpoints remain read-only. A write operation requires two explicit POSTs:
prepare creates a short-lived one-time token for an executable plan; execute
rebuilds and compares the plan, rechecks blockers, consumes the token, and only
then submits the validated G-code script to Moonraker.
"""

import json
import secrets
import threading
import time
import urllib.parse
import urllib.request

import ifs_spoolman as core
import ifs_spoolman_control as control
import ifs_spoolman_local as local
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.14-beta"
_BaseHandler = core.Handler
TOKEN_TTL_SECONDS = 90
CONFIRMATION_PHRASE = "EXECUTE_IFS_OPERATION"

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

_token_lock = threading.RLock()
_pending_tokens = {}
_execution_lock = threading.Lock()


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


def _validated_warnings(readiness):
    return [
        item for item in readiness.get("warnings", [])
        if item.get("code") != "control_macro_contract_unverified"
    ]


def operation_plan(action, slot=None, material=None, temperature=None):
    action = str(action or "").strip().lower()
    aliases = {"load": "load", "switch": "switch", "change": "switch", "unload": "unload"}
    if action not in aliases:
        raise ValueError("action должен быть load, switch или unload")
    action = aliases[action]

    readiness, cached = _runtime_snapshot()
    blockers = list(readiness.get("blockers", []))
    warnings = _validated_warnings(readiness)
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
        "control_enabled": True,
        "write_endpoints_enabled": True,
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
            "available": not blockers,
            "prepare_endpoint": "/api/ifs/control/prepare",
            "execute_endpoint": "/api/ifs/control/execute",
            "token_ttl_seconds": TOKEN_TTL_SECONDS,
            "confirmation_phrase": CONFIRMATION_PHRASE,
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
        "control_enabled": True,
        "write_endpoints_enabled": True,
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
        "execution_protocol": {
            "prepare": "POST /api/ifs/control/prepare",
            "execute": "POST /api/ifs/control/execute",
            "token_ttl_seconds": TOKEN_TTL_SECONDS,
            "confirmation_phrase": CONFIRMATION_PHRASE,
        },
    }


def _purge_expired_tokens():
    now = time.monotonic()
    expired = [token for token, entry in _pending_tokens.items() if entry["expires_at"] <= now]
    for token in expired:
        _pending_tokens.pop(token, None)


def prepare_operation(body):
    plan = operation_plan(
        action=body.get("action"),
        slot=body.get("slot"),
        material=body.get("material"),
        temperature=body.get("temperature"),
    )
    if not plan["plan_executable"]:
        raise RuntimeError("Операция заблокирована: " + "; ".join(
            item.get("message", item.get("code", "unknown")) for item in plan["blockers"]
        ))

    token = secrets.token_urlsafe(24)
    now = time.monotonic()
    entry = {
        "created_at": now,
        "expires_at": now + TOKEN_TTL_SECONDS,
        "request": {
            "action": plan["action"],
            "slot": plan["target_slot"],
            "material": plan["material"],
            "temperature": plan["temperature"],
        },
        "gcode_preview": plan["gcode_preview"],
        "active_slot": plan["active_slot"],
        "target_presence": plan["target_slot_state"].get("filament_present"),
    }
    with _token_lock:
        _purge_expired_tokens()
        _pending_tokens.clear()
        _pending_tokens[token] = entry

    core.event_log(
        "info", "ifs_operation_prepared", "Операция IFS подготовлена",
        action=plan["action"], target_slot=plan["target_slot"],
        gcode=plan["gcode_preview"], expires_in=TOKEN_TTL_SECONDS,
    )
    return {
        "prepared": True,
        "executed": False,
        "token": token,
        "expires_in_seconds": TOKEN_TTL_SECONDS,
        "confirmation_phrase": CONFIRMATION_PHRASE,
        "plan": plan,
    }


def _submit_gcode(script):
    url = core.MOONRAKER + "/printer/gcode/script"
    request = urllib.request.Request(
        url,
        data=json.dumps({"script": script}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=max(float(core.HTTP_TIMEOUT), 10.0)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or "error" in payload:
        raise RuntimeError(f"Moonraker отклонил G-code: {payload}")
    return payload


def execute_operation(body):
    token = str(body.get("token") or "").strip()
    confirmation = str(body.get("confirmation") or "").strip()
    if not token:
        raise ValueError("Не указан одноразовый token")
    if confirmation != CONFIRMATION_PHRASE:
        raise ValueError("Неверная строка подтверждения")

    with _execution_lock:
        with _token_lock:
            _purge_expired_tokens()
            entry = _pending_tokens.pop(token, None)
        if entry is None:
            raise RuntimeError("Токен отсутствует, уже использован или истёк")

        plan = operation_plan(**entry["request"])
        if not plan["plan_executable"]:
            raise RuntimeError("Состояние изменилось, операция теперь заблокирована")
        if plan["active_slot"] != entry["active_slot"]:
            raise RuntimeError("Активный слот изменился после подготовки операции")
        if plan["gcode_preview"] != entry["gcode_preview"]:
            raise RuntimeError("План операции изменился после подготовки")
        if plan["target_slot_state"].get("filament_present") != entry["target_presence"]:
            raise RuntimeError("Состояние датчика целевого слота изменилось")

        response = _submit_gcode(plan["gcode_preview"])
        core.event_log(
            "warning", "ifs_operation_submitted", "Команда IFS отправлена в Moonraker",
            action=plan["action"], target_slot=plan["target_slot"],
            gcode=plan["gcode_preview"],
        )
        return {
            "accepted": True,
            "executed": True,
            "submitted_at": core.timestamp_now(),
            "gcode": plan["gcode_preview"],
            "plan": plan,
            "moonraker": response,
            "note": "Moonraker принял команду; механическая операция выполняется асинхронно",
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

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/ifs/control/prepare":
            try:
                self.send_json(200, prepare_operation(self.read_json()))
            except ValueError as exc:
                self.send_json(400, {"error": str(exc), "gcode_executed": False})
            except RuntimeError as exc:
                self.send_json(409, {"error": str(exc), "gcode_executed": False})
            except Exception as exc:
                self.send_json(500, {"error": str(exc), "gcode_executed": False})
            return
        if path == "/api/ifs/control/execute":
            try:
                self.send_json(202, execute_operation(self.read_json()))
            except ValueError as exc:
                self.send_json(400, {"error": str(exc), "gcode_executed": False})
            except RuntimeError as exc:
                self.send_json(409, {"error": str(exc), "gcode_executed": False})
            except Exception as exc:
                self.send_json(500, {"error": str(exc), "gcode_executed": False})
            return
        super().do_POST()


runtime.RUNTIME_VERSION = RUNTIME_VERSION
local.RUNTIME_VERSION = RUNTIME_VERSION
control.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = PlannerRuntimeHandler


if __name__ == "__main__":
    core.main()
