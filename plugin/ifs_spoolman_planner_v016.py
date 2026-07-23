#!/usr/bin/env python3
"""Guarded two-phase execution layer for AD5X IFS control.

Prepared plan metadata is persisted for diagnostics, but the executable token is
kept only in process memory.  A service restart therefore invalidates every
prepared physical operation instead of allowing an old token to execute later.
"""

import copy
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_control as control
import ifs_spoolman_local as local
import ifs_spoolman_planner as planner
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.16-beta"
_BaseHandler = planner.PlannerRuntimeHandler
STATE_SCHEMA = "ifs-pending-operation-v2"
PENDING_STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "pending_operation.json",
)
_pending_state_lock = threading.RLock()
_pending_token_lock = threading.RLock()
_pending_tokens = {}
planner.TOKEN_TTL_SECONDS = 300


class ControlApiError(Exception):
    """HTTP-safe control error with a stable machine-readable code."""

    def __init__(self, code, message, status=409, details=None):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.status = int(status)
        self.details = details

    def payload(self):
        error = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            error["details"] = self.details
        return {
            "accepted": False,
            "prepared": False,
            "gcode_executed": False,
            "error": error,
        }


def _atomic_write_json(path, payload):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _clear_pending_token(operation_id=None):
    with _pending_token_lock:
        if operation_id is None:
            _pending_tokens.clear()
        else:
            _pending_tokens.pop(str(operation_id), None)


def _clear_pending_state(operation_id=None):
    with _pending_state_lock:
        try:
            os.remove(PENDING_STATE_PATH)
        except FileNotFoundError:
            pass
    _clear_pending_token(operation_id)


def _load_pending_state():
    with _pending_state_lock:
        try:
            with open(PENDING_STATE_PATH, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError) as exc:
            _clear_pending_state()
            raise ControlApiError(
                "prepared_operation_state_corrupt",
                "Сохранённое состояние подготовленной операции повреждено",
                status=409,
                details=str(exc),
            )

    if not isinstance(payload, dict) or payload.get("schema") != STATE_SCHEMA:
        _clear_pending_state()
        raise ControlApiError(
            "prepared_operation_state_invalid",
            "Сохранённое состояние подготовленной операции имеет неверный формат",
            status=409,
        )
    return payload


def _save_pending_state(payload):
    with _pending_state_lock:
        _atomic_write_json(PENDING_STATE_PATH, payload)


def _canonical_hash(payload):
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _plan_identity(plan):
    return {
        "action": plan.get("action"),
        "active_slot": plan.get("active_slot"),
        "target_slot": plan.get("target_slot"),
        "material": plan.get("material"),
        "temperature": plan.get("temperature"),
        "macro": plan.get("macro"),
        "parameters": plan.get("parameters"),
        "gcode_preview": plan.get("gcode_preview"),
        "target_presence": (
            plan.get("target_slot_state", {}).get("filament_present")
        ),
    }


def _pending_expired(state):
    try:
        return float(state.get("expires_at_epoch")) <= time.time()
    except (TypeError, ValueError):
        return True


def _token_for_operation(operation_id):
    with _pending_token_lock:
        return _pending_tokens.get(str(operation_id))


def _validated_contract_available(readiness):
    macros = readiness.get("macros", {})
    related = {
        str(name).lower()
        for name in macros.get("related_registered_macros", [])
    }
    return {
        "gcode_macro _insert_prutok_ifs",
        "gcode_macro _remove_prutok_ifs",
    }.issubset(related)


_original_control_readiness = control.control_readiness


def validated_control_readiness():
    payload = _original_control_readiness()
    if not _validated_contract_available(payload):
        return payload

    result = copy.deepcopy(payload)
    result["version"] = RUNTIME_VERSION
    result["contract_selected"] = True
    result["control_enabled"] = True
    result["write_endpoints_enabled"] = True
    result["ready_for_commands"] = not bool(result.get("blockers"))
    result["macro_contract_endpoint"] = "/api/ifs/control/contract"

    macros = result.setdefault("macros", {})
    macros["required_contract_selected"] = True
    result["warnings"] = [
        item
        for item in result.get("warnings", [])
        if item.get("code") != "control_macro_contract_unverified"
    ]
    return result


control.control_readiness = validated_control_readiness


def _raise_plan_blocked(plan):
    blockers = list(plan.get("blockers", []))
    first = blockers[0] if blockers else {}
    raise ControlApiError(
        first.get("code", "operation_blocked"),
        first.get("message", "Операция IFS заблокирована"),
        status=409,
        details={"blockers": blockers},
    )


def prepare_operation(body):
    if planner._operation_busy():
        raise ControlApiError(
            "operation_in_progress",
            "Предыдущая операция IFS ещё выполняется",
            status=409,
        )

    plan = planner.operation_plan(
        action=body.get("action"),
        slot=body.get("slot"),
        material=body.get("material"),
        temperature=body.get("temperature"),
    )
    if not plan.get("plan_executable"):
        _raise_plan_blocked(plan)

    operation_id = secrets.token_urlsafe(12)
    token = secrets.token_urlsafe(24)
    now_epoch = time.time()
    identity = _plan_identity(plan)
    state = {
        "schema": STATE_SCHEMA,
        "version": RUNTIME_VERSION,
        "status": "prepared",
        "operation_id": operation_id,
        "created_at": core.timestamp_now(),
        "created_at_epoch": now_epoch,
        "expires_at_epoch": now_epoch + planner.TOKEN_TTL_SECONDS,
        "request": {
            "action": plan["action"],
            "slot": plan["target_slot"],
            "material": plan["material"],
            "temperature": plan["temperature"],
        },
        "active_slot": plan["active_slot"],
        "target_presence": identity["target_presence"],
        "gcode_preview": plan["gcode_preview"],
        "plan_hash": _canonical_hash(identity),
        "token_persistence": "memory_only",
        "tokens_survive_restart": False,
    }
    with _pending_token_lock:
        _pending_tokens.clear()
        _pending_tokens[operation_id] = token
    _save_pending_state(state)

    core.event_log(
        "info",
        "ifs_operation_prepared_guarded",
        "Операция IFS подготовлена; token сохранён только в памяти",
        operation_id=operation_id,
        action=plan["action"],
        target_slot=plan["target_slot"],
        gcode=plan["gcode_preview"],
        expires_in=planner.TOKEN_TTL_SECONDS,
    )
    return {
        "prepared": True,
        "executed": False,
        "operation_id": operation_id,
        "token": token,
        "expires_in_seconds": planner.TOKEN_TTL_SECONDS,
        "confirmation_phrase": planner.CONFIRMATION_PHRASE,
        "persistent_state": True,
        "token_persistence": "memory_only",
        "tokens_survive_restart": False,
        "plan": plan,
    }


def _validated_pending_state(token):
    state = _load_pending_state()
    if state is None:
        raise ControlApiError(
            "prepared_operation_not_found",
            "Подготовленная операция отсутствует или уже использована",
            status=409,
        )
    operation_id = str(state.get("operation_id") or "")
    if _pending_expired(state):
        _clear_pending_state(operation_id)
        raise ControlApiError(
            "prepared_operation_expired",
            "Срок действия подготовленной операции истёк",
            status=409,
        )
    expected = _token_for_operation(operation_id)
    if not expected:
        _clear_pending_state(operation_id)
        raise ControlApiError(
            "prepared_operation_restart_invalidated",
            "Подготовленная операция аннулирована перезапуском сервиса",
            status=409,
        )
    if not secrets.compare_digest(expected, token):
        raise ControlApiError(
            "token_mismatch",
            "Одноразовый токен не соответствует подготовленной операции",
            status=409,
        )
    return state


def execute_operation(body):
    token = str(body.get("token") or "").strip()
    confirmation = str(body.get("confirmation") or "").strip()
    if not token:
        raise ControlApiError(
            "token_required",
            "Не указан одноразовый token",
            status=400,
        )
    if confirmation != planner.CONFIRMATION_PHRASE:
        raise ControlApiError(
            "confirmation_mismatch",
            "Неверная строка подтверждения",
            status=400,
        )
    if planner._operation_busy():
        raise ControlApiError(
            "operation_in_progress",
            "Предыдущая операция IFS ещё выполняется",
            status=409,
        )

    state = _validated_pending_state(token)
    plan = planner.operation_plan(**state["request"])
    if not plan.get("plan_executable"):
        raise ControlApiError(
            "state_changed_after_prepare",
            "Состояние изменилось, операция теперь заблокирована",
            status=409,
            details={"blockers": plan.get("blockers", [])},
        )

    current_identity = _plan_identity(plan)
    current_hash = _canonical_hash(current_identity)
    if plan.get("active_slot") != state.get("active_slot"):
        raise ControlApiError(
            "active_slot_changed",
            "Активный слот изменился после подготовки операции",
            status=409,
        )
    if current_hash != state.get("plan_hash"):
        raise ControlApiError(
            "plan_changed_after_prepare",
            "План операции изменился после подготовки",
            status=409,
            details={
                "prepared_gcode": state.get("gcode_preview"),
                "current_gcode": plan.get("gcode_preview"),
            },
        )
    if current_identity.get("target_presence") != state.get("target_presence"):
        raise ControlApiError(
            "target_presence_changed",
            "Состояние датчика целевого слота изменилось",
            status=409,
        )

    operation_id = str(state.get("operation_id") or secrets.token_urlsafe(12))
    created_at = core.timestamp_now()
    with planner._operation_lock:
        planner._operation.clear()
        planner._operation.update({
            "operation_id": operation_id,
            "status": "queued",
            "accepted": True,
            "gcode_submitted": False,
            "completed": False,
            "failed": False,
            "created_at": created_at,
            "started_at": None,
            "submitted_at": None,
            "completed_at": None,
            "updated_at": created_at,
            "action": plan["action"],
            "active_slot_before": plan["active_slot"],
            "target_slot": plan["target_slot"],
            "gcode": plan["gcode_preview"],
            "plan": plan,
            "moonraker": None,
            "error": None,
            "observed": {},
        })

    worker = threading.Thread(
        target=planner._operation_worker,
        args=(operation_id, plan),
        name=f"ifs-operation-{operation_id}",
        daemon=True,
    )
    try:
        worker.start()
    except Exception:
        with planner._operation_lock:
            planner._operation.update({
                "status": "failed",
                "failed": True,
                "completed_at": core.timestamp_now(),
            })
        raise

    _clear_pending_state(operation_id)
    core.event_log(
        "warning",
        "ifs_operation_queued_guarded",
        "Подготовленная операция IFS поставлена в фоновое выполнение",
        operation_id=operation_id,
        action=plan["action"],
        target_slot=plan["target_slot"],
        gcode=plan["gcode_preview"],
    )
    return {
        "accepted": True,
        "executed": False,
        "asynchronous": True,
        "operation_id": operation_id,
        "status": "queued",
        "status_endpoint": "/api/ifs/control/operation",
        "gcode": plan["gcode_preview"],
        "persistent_state_consumed": True,
        "token_persistence": "memory_only",
        "note": "Операция поставлена в фоновый worker; проверяйте status_endpoint",
    }


def operation_snapshot():
    payload = planner._operation_snapshot()
    if payload.get("status") in {"queued", "submitting", "running", "completed", "failed"}:
        payload["persistent_prepare_state"] = False
        payload["token_persistence"] = "memory_only"
        payload["tokens_survive_restart"] = False
        return payload

    try:
        state = _load_pending_state()
    except ControlApiError as exc:
        payload["pending_error"] = exc.payload()["error"]
        return payload

    if state is None:
        payload["persistent_prepare_state"] = False
        payload["token_persistence"] = "memory_only"
        payload["tokens_survive_restart"] = False
        return payload
    operation_id = str(state.get("operation_id") or "")
    if _pending_expired(state):
        _clear_pending_state(operation_id)
        payload["persistent_prepare_state"] = False
        payload["pending_error"] = {
            "code": "prepared_operation_expired",
            "message": "Срок действия подготовленной операции истёк",
        }
        return payload
    if not _token_for_operation(operation_id):
        _clear_pending_state(operation_id)
        payload["persistent_prepare_state"] = False
        payload["pending_error"] = {
            "code": "prepared_operation_restart_invalidated",
            "message": "Подготовленная операция аннулирована перезапуском сервиса",
        }
        payload["token_persistence"] = "memory_only"
        payload["tokens_survive_restart"] = False
        return payload

    payload.update({
        "operation_id": operation_id,
        "status": "prepared",
        "accepted": False,
        "created_at": state.get("created_at"),
        "updated_at": state.get("created_at"),
        "action": state.get("request", {}).get("action"),
        "active_slot_before": state.get("active_slot"),
        "target_slot": state.get("request", {}).get("slot"),
        "gcode": state.get("gcode_preview"),
        "persistent_prepare_state": True,
        "expires_at_epoch": state.get("expires_at_epoch"),
        "expires_in_seconds": max(
            0,
            int(float(state.get("expires_at_epoch", 0)) - time.time()),
        ),
        "token_persistence": "memory_only",
        "tokens_survive_restart": False,
    })
    return payload


class PersistentPlannerRuntimeHandler(_BaseHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/ifs/control/operation":
            self.send_json(200, operation_snapshot())
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/ifs/control/prepare":
            try:
                self.send_json(200, prepare_operation(self.read_json()))
            except ControlApiError as exc:
                self.send_json(exc.status, exc.payload())
            except ValueError as exc:
                error = ControlApiError("invalid_request", str(exc), status=400)
                self.send_json(400, error.payload())
            except Exception as exc:
                error = ControlApiError("prepare_internal_error", str(exc), status=500)
                self.send_json(500, error.payload())
            return
        if path == "/api/ifs/control/execute":
            try:
                self.send_json(202, execute_operation(self.read_json()))
            except ControlApiError as exc:
                self.send_json(exc.status, exc.payload())
            except ValueError as exc:
                error = ControlApiError("invalid_request", str(exc), status=400)
                self.send_json(400, error.payload())
            except Exception as exc:
                error = ControlApiError("execute_internal_error", str(exc), status=500)
                self.send_json(500, error.payload())
            return
        super().do_POST()


planner.RUNTIME_VERSION = RUNTIME_VERSION
runtime.RUNTIME_VERSION = RUNTIME_VERSION
local.RUNTIME_VERSION = RUNTIME_VERSION
control.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = PersistentPlannerRuntimeHandler


if __name__ == "__main__":
    core.main()
