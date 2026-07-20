#!/usr/bin/env python3
"""Phase B3: standalone web UI with physical IFS slot presence."""

import json
import os
import threading
import time
import urllib.parse
import urllib.request

import ifs_spoolman as core
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.7.6-beta"
MANAGER_HTML = os.path.join(core.APP_DIR, "zmod-filaments.html")
IFS_STATUS_CACHE_SECONDS = 1.0
IFS_STATUS_GCODE_COUNT = 100
_BaseHandler = writer.WriteRuntimeHandler
_original_public_config = writer.public_config
_original_build_health = writer.build_health
_ifs_lock = threading.RLock()
_ifs_cache = {"created_monotonic": 0.0, "payload": None}


def _moonraker_result(path):
    response = core.http_json(core.MOONRAKER + path)
    result = response.get("result", {})
    if not isinstance(result, dict):
        raise RuntimeError("Moonraker вернул неожиданный формат ответа")
    return result


def _run_gcode(script):
    body = json.dumps({"script": script}).encode("utf-8")
    request = urllib.request.Request(
        core.MOONRAKER + "/printer/gcode/script",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=core.HTTP_TIMEOUT) as response:
        payload = json.load(response)
    if payload.get("result") != "ok":
        raise RuntimeError("Moonraker не подтвердил выполнение IFS_STATUS")


def _extract_ifs_values(entries, started_at):
    for entry in reversed(entries):
        if not isinstance(entry, dict) or entry.get("type") != "response":
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
        if isinstance(values, dict) and {"State", "Ports", "Silk", "Chan"}.issubset(values):
            return values
    raise RuntimeError("Ответ IFS_STATUS не найден в журнале G-code")


def ifs_slot_status(force=False):
    now = time.monotonic()
    with _ifs_lock:
        cached = _ifs_cache["payload"]
        age = now - _ifs_cache["created_monotonic"]
        if not force and cached is not None and age < IFS_STATUS_CACHE_SECONDS:
            return dict(cached)

        try:
            started_at = time.time()
            _run_gcode("IFS_STATUS")
            result = _moonraker_result(
                "/server/gcode_store?count=" + str(IFS_STATUS_GCODE_COUNT)
            )
            entries = result.get("gcode_store", [])
            if not isinstance(entries, list):
                raise RuntimeError("Moonraker не вернул журнал G-code")
            values = _extract_ifs_values(entries, started_at)
            ports = values.get("Ports", [])
            if not isinstance(ports, list):
                ports = []
            slots = {}
            for slot in range(1, int(core.SLOT_COUNT) + 1):
                present = bool(ports[slot - 1]) if slot - 1 < len(ports) else False
                slots[str(slot)] = {
                    "slot": slot,
                    "filament_present": present,
                }
            payload = {
                "available": True,
                "checked_at": core.timestamp_now(),
                "source": "IFS_STATUS.Ports",
                "slots": slots,
                "active_slot": core.state_snapshot().get("active_slot"),
                "raw": values,
                "reason": None,
            }
        except Exception as exc:
            payload = {
                "available": False,
                "checked_at": core.timestamp_now(),
                "source": "IFS_STATUS.Ports",
                "slots": {
                    str(slot): {"slot": slot, "filament_present": None}
                    for slot in range(1, int(core.SLOT_COUNT) + 1)
                },
                "active_slot": core.state_snapshot().get("active_slot"),
                "reason": "ifs_status_probe_failed",
                "error": str(exc),
            }

        _ifs_cache["created_monotonic"] = time.monotonic()
        _ifs_cache["payload"] = dict(payload)
        return payload


def public_config():
    payload = _original_public_config()
    payload["application_version"] = RUNTIME_VERSION
    payload["zmod_metadata"]["manager_url"] = "/manager"
    payload["ifs_slots"] = {"endpoint": "/api/ifs/slots", "read_only": True}
    return payload


def build_health():
    health = _original_build_health()
    presence = ifs_slot_status()
    health["version"] = RUNTIME_VERSION
    health.setdefault("components", {}).setdefault("zmod_metadata", {})[
        "manager_url"
    ] = "/manager"
    health["components"]["ifs_slots"] = {
        "ok": presence.get("available") is True,
        "source": presence.get("source"),
        "reason": presence.get("reason"),
    }
    return health


class UiRuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path in {"/manager", "/manager/", "/zmod-filaments.html"}:
            try:
                with open(MANAGER_HTML, "rb") as stream:
                    raw = stream.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            except FileNotFoundError:
                self.send_json(404, {"error": "Страница менеджера не установлена"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if path == "/api/ifs/slots":
            force = query.get("refresh", [""])[0].lower() in {"1", "true", "yes"}
            self.send_json(200, ifs_slot_status(force=force))
            return
        super().do_GET()


writer.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.public_config = public_config
core.build_health = build_health
core.Handler = UiRuntimeHandler


if __name__ == "__main__":
    core.main()
