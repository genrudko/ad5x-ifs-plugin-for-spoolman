#!/usr/bin/env python3
"""Phase B1 runtime: optional inventory plus read-only Z-Mod metadata discovery.

The legacy backend remains intact. This wrapper keeps Spoolman optional and adds
safe, read-only discovery of native Z-Mod colour/material metadata. It does not
execute filament movement commands and does not write Z-Mod settings.
"""

import json
import os
import threading
import time
import urllib.parse

import ifs_spoolman as core


RUNTIME_VERSION = "0.7.1-beta"
INVENTORY_CONFIG_FILE = os.path.join(core.APP_DIR, "inventory.json")
VALID_PROVIDERS = {"auto", "none", "spoolman"}
ZMOD_METADATA_CACHE_SECONDS = 3.0
KNOWN_ZMOD_OBJECTS = (
    "zmod_color",
    "save_variables",
    "gcode_macro COLOR",
    "gcode_macro SET_CURRENT_PRUTOK",
)
KNOWN_METADATA_FILES = (
    "/usr/prog/config/Adventurer5M.json",
    "/root/printer_data/config/Adventurer5M.json",
    "/usr/data/config/Adventurer5M.json",
    "/opt/config/Adventurer5M.json",
)
METADATA_KEYWORDS = (
    "color",
    "colour",
    "material",
    "filament",
    "prutok",
    "slot",
    "channel",
    "type",
)

_metadata_lock = threading.RLock()
_metadata_cache = {
    "created_monotonic": 0.0,
    "payload": None,
}


def _atomic_write(path, payload):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _load_inventory_config():
    payload = {"provider": "auto"}
    try:
        with open(INVENTORY_CONFIG_FILE, "r", encoding="utf-8") as stream:
            raw = json.load(stream)
        if isinstance(raw, dict):
            payload.update(raw)
    except FileNotFoundError:
        _atomic_write(INVENTORY_CONFIG_FILE, payload)
    except Exception as exc:
        core.event_log(
            "warning",
            "inventory_config_invalid",
            "Не удалось прочитать inventory.json; используется auto",
            error=str(exc),
        )

    provider = str(payload.get("provider", "auto")).strip().lower()
    if provider not in VALID_PROVIDERS:
        provider = "auto"
    normalized = {"provider": provider}
    try:
        _atomic_write(INVENTORY_CONFIG_FILE, normalized)
    except Exception:
        pass
    return normalized


_inventory_config = _load_inventory_config()
_original_get_moonraker_status = core.get_moonraker_status
_original_set_active_spool = core.set_active_spool
_original_list_spools = core.list_spools
_original_synchronize = core.synchronize
_original_build_health = core.build_health
_original_public_config = core.public_config
_BaseHandler = core.Handler


def _probe_spoolman():
    try:
        result = _original_get_moonraker_status()
        return bool(result.get("spoolman_connected")), result
    except Exception as exc:
        return False, {"error": str(exc)}


def inventory_status():
    configured = _inventory_config["provider"]
    connected, moonraker = _probe_spoolman()

    if configured == "auto":
        effective = "spoolman" if connected else "none"
    else:
        effective = configured

    available = effective == "none" or connected
    return {
        "configured_provider": configured,
        "provider": effective,
        "available": available,
        "connected": connected if effective == "spoolman" else False,
        "external_service_required": effective == "spoolman",
        "fallback_active": configured == "auto" and effective == "none",
        "config_file": INVENTORY_CONFIG_FILE,
        "moonraker": moonraker,
    }


def _set_inventory_state(status):
    core.set_state(
        inventory_provider=status["provider"],
        inventory_configured_provider=status["configured_provider"],
        inventory_available=status["available"],
        spoolman_connected=status["connected"],
    )


def get_moonraker_status():
    status = inventory_status()
    _set_inventory_state(status)
    if status["provider"] == "none":
        return {
            "spoolman_connected": False,
            "spool_id": None,
            "inventory_provider": "none",
        }
    return _original_get_moonraker_status()


def set_active_spool(spool_id):
    status = inventory_status()
    _set_inventory_state(status)
    if status["provider"] != "spoolman":
        return None
    return _original_set_active_spool(spool_id)


def list_spools():
    status = inventory_status()
    _set_inventory_state(status)
    if status["provider"] == "none":
        return []
    if not status["connected"]:
        return []
    return _original_list_spools()


def synchronize(force=False, slot=None, reason="manual"):
    status = inventory_status()
    _set_inventory_state(status)

    if status["provider"] == "spoolman":
        return _original_synchronize(force=force, slot=slot, reason=reason)

    if slot is None:
        raw_slot = core.read_active_slot()
        slot, confirmation_values = core.confirm_active_slot(raw_slot)
        if slot is None:
            core.set_state(
                last_sync_reason="slot_not_confirmed",
                confirmation_values=confirmation_values,
            )
            if force:
                raise RuntimeError("Активный слот IFS не подтверждён")
            return False

    core.set_state(
        active_slot=slot,
        confirmed_active_slot=slot,
        desired_spool_id=None,
        moonraker_spool_id=None,
        moonraker_status_ok=True,
        spoolman_connected=False,
        last_error=None,
        last_sync_result="inventory_disabled",
        last_sync_reason=reason,
    )
    return False


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


def _query_objects(names):
    if not names:
        return {}
    query = urllib.parse.urlencode({name: "" for name in names})
    result = _moonraker_result("/printer/objects/query?" + query)
    status = result.get("status", {})
    return status if isinstance(status, dict) else {}


def _interesting(value, path="", depth=0):
    if depth > 8:
        return None
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            lowered = child_path.lower()
            keep_branch = any(word in lowered for word in METADATA_KEYWORDS)
            filtered = _interesting(child, child_path, depth + 1)
            if filtered not in (None, {}, []):
                result[key_text] = filtered
            elif keep_branch and child is not None and not isinstance(child, (dict, list)):
                result[key_text] = child
        return result or None
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value):
            filtered = _interesting(child, f"{path}[{index}]", depth + 1)
            if filtered not in (None, {}, []):
                result.append(filtered)
        return result or None
    if any(word in path.lower() for word in METADATA_KEYWORDS):
        return value
    return None


def _read_metadata_files():
    sources = []
    for path in KNOWN_METADATA_FILES:
        if not os.path.isfile(path):
            continue
        entry = {"path": path, "readable": True}
        try:
            with open(path, "r", encoding="utf-8") as stream:
                raw = json.load(stream)
            entry["candidates"] = _interesting(raw) or {}
        except Exception as exc:
            entry["readable"] = False
            entry["error"] = str(exc)
        sources.append(entry)
    return sources


def _slot_candidates(payload):
    slots = {str(index): {} for index in range(1, int(core.SLOT_COUNT) + 1)}

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
            return

        lowered = path.lower()
        if not any(word in lowered for word in ("color", "colour", "material", "filament", "prutok")):
            return
        for slot in slots:
            markers = (
                f"slot{slot}", f"slot_{slot}", f"slot.{slot}",
                f"channel{slot}", f"channel_{slot}", f"channel.{slot}",
                f"prutok{slot}", f"prutok_{slot}", f"prutok.{slot}",
                f"[{int(slot) - 1}]",
            )
            if any(marker in lowered for marker in markers):
                slots[slot][path] = value

    walk(payload)
    return slots


def zmod_filament_metadata(force=False):
    now = time.monotonic()
    with _metadata_lock:
        cached = _metadata_cache["payload"]
        age = now - _metadata_cache["created_monotonic"]
        if not force and cached is not None and age < ZMOD_METADATA_CACHE_SECONDS:
            return dict(cached)

        checked_at = core.timestamp_now()
        try:
            objects = _registered_objects()
            selected = [name for name in KNOWN_ZMOD_OBJECTS if name in objects]
            object_status = _query_objects(selected)
            interesting_objects = _interesting(object_status) or {}
            file_sources = _read_metadata_files()
            combined = {
                "objects": interesting_objects,
                "files": file_sources,
            }
            payload = {
                "available": bool(interesting_objects or file_sources),
                "read_only": True,
                "write_actions_enabled": False,
                "checked_at": checked_at,
                "cache_ttl_seconds": ZMOD_METADATA_CACHE_SECONDS,
                "registered_candidates": selected,
                "registered_zmod_objects": [
                    name for name in objects if "zmod" in name.lower()
                ],
                "sources": combined,
                "slots": _slot_candidates(combined),
                "active_slot": core.state_snapshot().get("active_slot"),
                "reason": None if (interesting_objects or file_sources) else "metadata_source_not_found",
            }
        except Exception as exc:
            payload = {
                "available": False,
                "read_only": True,
                "write_actions_enabled": False,
                "checked_at": checked_at,
                "cache_ttl_seconds": ZMOD_METADATA_CACHE_SECONDS,
                "registered_candidates": [],
                "registered_zmod_objects": [],
                "sources": {"objects": {}, "files": []},
                "slots": {str(index): {} for index in range(1, int(core.SLOT_COUNT) + 1)},
                "active_slot": core.state_snapshot().get("active_slot"),
                "reason": "metadata_probe_failed",
                "error": str(exc),
            }

        _metadata_cache["created_monotonic"] = time.monotonic()
        _metadata_cache["payload"] = dict(payload)
        return payload


def public_config():
    payload = _original_public_config()
    payload["application"] = "AD5X IFS Manager"
    payload["application_version"] = RUNTIME_VERSION
    payload["inventory"] = inventory_status()
    payload["zmod_metadata"] = {
        "endpoint": "/api/zmod/filaments",
        "read_only": True,
        "write_actions_enabled": False,
    }
    return payload


def build_health():
    health = _original_build_health()
    status = inventory_status()
    metadata = zmod_filament_metadata()
    _set_inventory_state(status)

    health["application"] = "AD5X IFS Manager"
    health["version"] = RUNTIME_VERSION
    health.setdefault("components", {})["inventory"] = {
        "ok": status["available"],
        "provider": status["provider"],
        "configured_provider": status["configured_provider"],
        "connected": status["connected"],
        "fallback_active": status["fallback_active"],
    }
    health["components"]["zmod_metadata"] = {
        "ok": metadata["available"],
        "read_only": True,
        "registered_candidates": metadata.get("registered_candidates", []),
        "source_file_count": len(metadata.get("sources", {}).get("files", [])),
        "reason": metadata.get("reason"),
    }

    sensor_ok = health["components"].get("ifs_sensor", {}).get("ok") is True
    moonraker_ok = health["components"].get("moonraker", {}).get("ok") is True
    last_error = health.get("last_error")
    if sensor_ok and moonraker_ok and status["available"] and not last_error:
        health["status"] = "ok"
    elif sensor_ok and moonraker_ok:
        health["status"] = "degraded"
    return health


class RuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/api/inventory/status":
            self.send_json(200, inventory_status())
            return
        if path == "/api/zmod/filaments":
            force = query.get("refresh", [""])[0].lower() in {"1", "true", "yes"}
            self.send_json(200, zmod_filament_metadata(force=force))
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/inventory/provider":
            try:
                body = self.read_json()
                provider = str(body.get("provider", "")).strip().lower()
                if provider not in VALID_PROVIDERS:
                    raise ValueError("provider должен быть auto, none или spoolman")
                _inventory_config["provider"] = provider
                _atomic_write(INVENTORY_CONFIG_FILE, _inventory_config)
                status = inventory_status()
                _set_inventory_state(status)
                self.send_json(200, {"ok": True, "inventory": status})
            except Exception as exc:
                self.send_json(400, {"error": str(exc)})
            return
        super().do_POST()


core.APP_VERSION = RUNTIME_VERSION
core.get_moonraker_status = get_moonraker_status
core.set_active_spool = set_active_spool
core.list_spools = list_spools
core.synchronize = synchronize
core.public_config = public_config
core.build_health = build_health
core.Handler = RuntimeHandler
_set_inventory_state(inventory_status())


if __name__ == "__main__":
    core.main()
