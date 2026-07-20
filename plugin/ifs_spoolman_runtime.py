#!/usr/bin/env python3
"""Phase B0 runtime: IFS works with optional Spoolman inventory.

The legacy backend remains intact. This wrapper adds an inventory-provider
layer and disables Spoolman synchronization cleanly when the provider is
`none`. Supported configured values: auto, none, spoolman.
"""

import json
import os
import urllib.parse

import ifs_spoolman as core


RUNTIME_VERSION = "0.7.0-beta"
INVENTORY_CONFIG_FILE = os.path.join(core.APP_DIR, "inventory.json")
VALID_PROVIDERS = {"auto", "none", "spoolman"}


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


def public_config():
    payload = _original_public_config()
    payload["application"] = "AD5X IFS Manager"
    payload["application_version"] = RUNTIME_VERSION
    payload["inventory"] = inventory_status()
    return payload


def build_health():
    health = _original_build_health()
    status = inventory_status()
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
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/inventory/status":
            self.send_json(200, inventory_status())
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
