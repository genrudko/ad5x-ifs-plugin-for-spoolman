#!/usr/bin/env python3
"""Standalone web UI with resilient physical IFS slot presence polling."""

import json
import os
import threading
import time
import urllib.parse
import urllib.request

import ifs_spoolman as core
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.7.11-beta"
MANAGER_HTML = os.path.join(core.APP_DIR, "zmod-filaments.html")
MANAGER_LIVE_JS = os.path.join(core.APP_DIR, "zmod-filaments-live.js")
IFS_STATUS_CACHE_SECONDS = 1.0
IFS_STATUS_GCODE_COUNT = 1000
IFS_STATUS_POLL_ATTEMPTS = 10
IFS_STATUS_POLL_INTERVAL = 0.3
IFS_STATUS_HTTP_TIMEOUT = max(float(core.HTTP_TIMEOUT), 15.0)
_BaseHandler = writer.WriteRuntimeHandler
_original_public_config = writer.public_config
_original_build_health = writer.build_health
_ifs_lock = threading.RLock()
_ifs_cache = {"created_monotonic": 0.0, "payload": None}
_ifs_last_success = {"payload": None}


def _moonraker_result(path, timeout=None):
    response = core.http_json(
        core.MOONRAKER + path,
        timeout=timeout or IFS_STATUS_HTTP_TIMEOUT,
    )
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
    with urllib.request.urlopen(request, timeout=IFS_STATUS_HTTP_TIMEOUT) as response:
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
        if entry_time + 0.1 < started_at:
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
    return None


def _wait_for_ifs_values(started_at):
    last_error = None
    for attempt in range(IFS_STATUS_POLL_ATTEMPTS):
        try:
            result = _moonraker_result(
                "/server/gcode_store?count=" + str(IFS_STATUS_GCODE_COUNT)
            )
            entries = result.get("gcode_store", [])
            if not isinstance(entries, list):
                raise RuntimeError("Moonraker не вернул журнал G-code")
            values = _extract_ifs_values(entries, started_at)
            if values is not None:
                return values
        except Exception as exc:
            last_error = exc
        if attempt + 1 < IFS_STATUS_POLL_ATTEMPTS:
            time.sleep(IFS_STATUS_POLL_INTERVAL)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Ответ IFS_STATUS не появился в журнале G-code")


def _slots_from_values(values):
    ports = values.get("Ports", [])
    if not isinstance(ports, list):
        raise RuntimeError("IFS_STATUS вернул некорректное поле Ports")
    slots = {}
    for slot in range(1, int(core.SLOT_COUNT) + 1):
        present = bool(ports[slot - 1]) if slot - 1 < len(ports) else False
        slots[str(slot)] = {
            "slot": slot,
            "filament_present": present,
        }
    return slots


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
            values = _wait_for_ifs_values(started_at)
            payload = {
                "available": True,
                "stale": False,
                "checked_at": core.timestamp_now(),
                "source": "IFS_STATUS.Ports",
                "slots": _slots_from_values(values),
                "active_slot": core.state_snapshot().get("active_slot"),
                "raw": values,
                "reason": None,
            }
            _ifs_last_success["payload"] = dict(payload)
        except Exception as exc:
            previous = _ifs_last_success.get("payload")
            if previous is not None:
                payload = dict(previous)
                payload.update(
                    {
                        "available": False,
                        "stale": True,
                        "checked_at": core.timestamp_now(),
                        "reason": "ifs_status_probe_failed",
                        "error": str(exc),
                        "last_success_at": previous.get("checked_at"),
                    }
                )
            else:
                payload = {
                    "available": False,
                    "stale": False,
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
    payload["zmod_metadata"]["auto_refresh_seconds"] = 8
    payload["ifs_slots"] = {"endpoint": "/api/ifs/slots", "read_only": True}
    return payload


def build_health():
    health = _original_build_health()
    presence = ifs_slot_status()
    health["version"] = RUNTIME_VERSION
    health.setdefault("components", {}).setdefault("zmod_metadata", {})[
        "manager_url"
    ] = "/manager"
    health["components"]["zmod_metadata"]["auto_refresh_seconds"] = 8
    health["components"]["ifs_slots"] = {
        "ok": presence.get("available") is True,
        "stale": presence.get("stale") is True,
        "source": presence.get("source"),
        "reason": presence.get("reason"),
    }
    return health


def _send_static(handler, path, content_type):
    with open(path, "rb") as stream:
        raw = stream.read()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)


class UiRuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path in {"/manager", "/manager/", "/zmod-filaments.html"}:
            try:
                with open(MANAGER_HTML, "r", encoding="utf-8") as stream:
                    text = stream.read()
                live_tag = '<script defer src="/zmod-filaments-live.js"></script>'
                if live_tag not in text:
                    text = text.replace("</body>", live_tag + "\n</body>", 1)
                raw = text.encode("utf-8")
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
        if path == "/zmod-filaments-live.js":
            try:
                _send_static(self, MANAGER_LIVE_JS, "application/javascript; charset=utf-8")
            except FileNotFoundError:
                self.send_json(404, {"error": "Скрипт автообновления не установлен"})
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
