#!/usr/bin/env python3
"""Phase B4: use verified local inventory as the auto-provider fallback."""

import os
import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.3-beta"
PROVIDER_UI_JS = os.path.join(core.APP_DIR, "zmod-inventory-provider.js")
_BaseHandler = ui.UiRuntimeHandler
_original_probe_spoolman = runtime._probe_spoolman
_original_get_moonraker_status = runtime._original_get_moonraker_status
_original_set_active_spool = runtime._original_set_active_spool
_original_list_spools = runtime._original_list_spools
_original_synchronize = runtime._original_synchronize

runtime.VALID_PROVIDERS.add("local")


def inventory_status():
    configured = runtime._inventory_config["provider"]
    connected, moonraker = _original_probe_spoolman()

    if configured == "auto":
        effective = "spoolman" if connected else "local"
    else:
        effective = configured

    available = effective in {"none", "local"} or connected
    return {
        "configured_provider": configured,
        "provider": effective,
        "available": available,
        "connected": connected if effective == "spoolman" else False,
        "local_available": True,
        "external_service_required": effective == "spoolman",
        "fallback_active": configured == "auto" and effective == "local",
        "config_file": runtime.INVENTORY_CONFIG_FILE,
        "moonraker": moonraker,
        "supported_providers": ["auto", "local", "spoolman", "none"],
    }


def local_inventory(force=False):
    metadata = runtime.zmod_filament_metadata(force=force)
    presence = ui.ifs_slot_status(force=force)
    slots = {}

    for slot in range(1, int(core.SLOT_COUNT) + 1):
        key = str(slot)
        metadata_slot = metadata.get("slots", {}).get(key, {})
        presence_slot = presence.get("slots", {}).get(key, {})
        slots[key] = {
            "id": f"local-{slot}",
            "slot": slot,
            "name": f"IFS {slot}",
            "color": metadata_slot.get("color"),
            "material": metadata_slot.get("material"),
            "filament_present": presence_slot.get("filament_present"),
            "active": int(metadata.get("active_slot") or 0) == slot,
        }

    return {
        "provider": "local",
        "available": metadata.get("available") is True,
        "read_only_inventory": False,
        "source": "Z-Mod FFMInfo + IFS_STATUS.Ports",
        "active_slot": metadata.get("active_slot"),
        "stale": presence.get("stale") is True,
        "slots": slots,
        "reason": metadata.get("reason"),
    }


def get_moonraker_status():
    status = inventory_status()
    runtime._set_inventory_state(status)
    if status["provider"] in {"none", "local"}:
        return {
            "spoolman_connected": False,
            "spool_id": None,
            "inventory_provider": status["provider"],
        }
    return _original_get_moonraker_status()


def set_active_spool(spool_id):
    status = inventory_status()
    runtime._set_inventory_state(status)
    if status["provider"] != "spoolman":
        return None
    return _original_set_active_spool(spool_id)


def list_spools():
    status = inventory_status()
    runtime._set_inventory_state(status)
    if status["provider"] != "spoolman" or not status["connected"]:
        return []
    return _original_list_spools()


def synchronize(force=False, slot=None, reason="manual"):
    status = inventory_status()
    runtime._set_inventory_state(status)

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
        last_sync_result=(
            "local_inventory_active"
            if status["provider"] == "local"
            else "inventory_disabled"
        ),
        last_sync_reason=reason,
    )
    return False


def _send_manager(handler):
    with open(ui.MANAGER_HTML, "r", encoding="utf-8") as stream:
        text = stream.read()
    tags = (
        '<script defer src="/zmod-filaments-live.js"></script>',
        '<script defer src="/zmod-inventory-provider.js"></script>',
    )
    for tag in tags:
        if tag not in text:
            text = text.replace("</body>", tag + "\n</body>", 1)
    raw = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)


class LocalRuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path in {"/manager", "/manager/", "/zmod-filaments.html"}:
            try:
                _send_manager(self)
            except FileNotFoundError:
                self.send_json(404, {"error": "Страница менеджера не установлена"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if path == "/zmod-inventory-provider.js":
            try:
                ui._send_static(self, PROVIDER_UI_JS, "application/javascript; charset=utf-8")
            except FileNotFoundError:
                self.send_json(404, {"error": "Скрипт выбора провайдера не установлен"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if path == "/api/inventory/local":
            query = urllib.parse.parse_qs(parsed.query)
            force = query.get("refresh", [""])[0].lower() in {"1", "true", "yes"}
            try:
                self.send_json(200, local_inventory(force=force))
            except Exception as exc:
                core.event_log(
                    "error",
                    "local_inventory_read_failed",
                    "Не удалось сформировать локальный инвентарь",
                    error=str(exc),
                )
                self.send_json(500, {"error": str(exc)})
            return
        super().do_GET()


runtime.inventory_status = inventory_status
runtime.get_moonraker_status = get_moonraker_status
runtime.set_active_spool = set_active_spool
runtime.list_spools = list_spools
runtime.synchronize = synchronize
runtime.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.get_moonraker_status = get_moonraker_status
core.set_active_spool = set_active_spool
core.list_spools = list_spools
core.synchronize = synchronize
core.Handler = LocalRuntimeHandler
runtime._set_inventory_state(inventory_status())


if __name__ == "__main__":
    core.main()
