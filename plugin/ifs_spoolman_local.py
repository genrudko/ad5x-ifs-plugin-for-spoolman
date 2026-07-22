#!/usr/bin/env python3
"""Local inventory, provider UI, event refresh and combined read-only inventory."""

import os
import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.5-beta"
PROVIDER_UI_JS = os.path.join(core.APP_DIR, "zmod-inventory-provider.js")
COMBINED_UI_JS = os.path.join(core.APP_DIR, "zmod-combined-inventory.js")
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
    effective = "spoolman" if configured == "auto" and connected else (
        "local" if configured == "auto" else configured
    )
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


def printer_activity():
    print_state = "unknown"
    filename = None
    error = None
    try:
        response = core.http_json(
            core.MOONRAKER + "/printer/objects/query?print_stats=state,filename",
            timeout=max(float(core.HTTP_TIMEOUT), 3.0),
        )
        status = response.get("result", {}).get("status", {})
        print_stats = status.get("print_stats", {})
        if isinstance(print_stats, dict):
            print_state = str(print_stats.get("state") or "unknown").lower()
            filename = print_stats.get("filename")
    except Exception as exc:
        error = str(exc)

    snapshot = core.state_snapshot()
    active_slot = snapshot.get("confirmed_active_slot")
    if active_slot is None:
        active_slot = snapshot.get("active_slot")
    return {
        "print_state": print_state,
        "printing": print_state in {"printing", "paused"},
        "filename": filename,
        "active_slot": active_slot,
        "source": "Moonraker print_stats + plugin state",
        "gcode_executed": False,
        "error": error,
    }


def local_inventory(force=False):
    metadata = runtime.zmod_filament_metadata(force=force)
    presence = ui.ifs_slot_status(force=force)
    slots = {}
    active_slot = metadata.get("active_slot") or presence.get("active_slot")
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
            "active": int(active_slot or 0) == slot,
        }
    return {
        "provider": "local",
        "available": metadata.get("available") is True,
        "read_only_inventory": False,
        "source": "Z-Mod FFMInfo + IFS_STATUS.Ports",
        "active_slot": active_slot,
        "stale": presence.get("stale") is True,
        "slots": slots,
        "reason": metadata.get("reason"),
    }


def _cached_local_inventory():
    """Build local state without issuing IFS_STATUS or any other G-code."""
    metadata = runtime.zmod_filament_metadata(force=False)
    cached_presence = ui._ifs_cache.get("payload") or {}
    snapshot = core.state_snapshot()
    active_slot = metadata.get("active_slot")
    if active_slot is None:
        active_slot = snapshot.get("confirmed_active_slot") or snapshot.get("active_slot")
    slots = {}
    for slot in range(1, int(core.SLOT_COUNT) + 1):
        key = str(slot)
        meta = metadata.get("slots", {}).get(key, {})
        physical = cached_presence.get("slots", {}).get(key, {})
        slots[key] = {
            "slot": slot,
            "color": meta.get("color"),
            "material": meta.get("material"),
            "filament_present": physical.get("filament_present"),
            "active": int(active_slot or 0) == slot,
        }
    return {
        "available": metadata.get("available") is True,
        "active_slot": active_slot,
        "stale": cached_presence.get("stale") is True,
        "presence_cached": bool(cached_presence),
        "slots": slots,
    }


def _normalize_hex(value):
    text = str(value or "").strip().lstrip("#")
    if len(text) not in {6, 8}:
        return None
    if any(char not in "0123456789abcdefABCDEF" for char in text):
        return None
    return "#" + text[:6].upper()


def _inventory_spool(spool):
    filament = spool.get("filament", {}) if isinstance(spool, dict) else {}
    vendor = filament.get("vendor", {}) if isinstance(filament, dict) else {}
    return {
        "assigned": True,
        "spool_id": spool.get("id"),
        "name": filament.get("name"),
        "vendor": vendor.get("name") if isinstance(vendor, dict) else None,
        "material": filament.get("material"),
        "color_hex": filament.get("color_hex"),
        "multi_color_hexes": filament.get("multi_color_hexes"),
        "remaining_weight": spool.get("remaining_weight"),
        "initial_weight": spool.get("initial_weight"),
        "archived": bool(spool.get("archived")),
    }


def combined_inventory():
    """Read-only aggregate. Never executes IFS_STATUS or writes either system."""
    status = inventory_status()
    local = _cached_local_inventory()
    assignments = dict(getattr(core, "assignments", {}) or {})
    spools = []
    error = None
    if status["provider"] == "spoolman" and status["connected"]:
        try:
            spools = _original_list_spools()
        except Exception as exc:
            error = str(exc)
    spool_by_id = {
        int(item.get("id")): item
        for item in spools
        if isinstance(item, dict) and item.get("id") is not None
    }

    slots = {}
    for slot in range(1, int(core.SLOT_COUNT) + 1):
        key = str(slot)
        local_slot = local["slots"].get(key, {})
        assigned_id = assignments.get(key)
        try:
            assigned_id = int(assigned_id) if assigned_id not in (None, "") else None
        except (TypeError, ValueError):
            assigned_id = None
        spool = spool_by_id.get(assigned_id)
        inventory = _inventory_spool(spool) if spool else {
            "assigned": assigned_id is not None,
            "spool_id": assigned_id,
        }
        local_material = str(local_slot.get("material") or "").strip().lower()
        spool_material = str(inventory.get("material") or "").strip().lower()
        local_color = _normalize_hex(local_slot.get("color"))
        spool_color = _normalize_hex(inventory.get("color_hex"))
        mismatch = bool(spool) and (
            bool(local_material and spool_material and local_material != spool_material)
            or bool(local_color and spool_color and local_color != spool_color)
        )
        slots[key] = {
            "slot": slot,
            "provider": status["provider"],
            "inventory_available": status["connected"] if status["provider"] == "spoolman" else True,
            "local": local_slot,
            "inventory": inventory,
            "mismatch": mismatch,
        }

    return {
        "read_only": True,
        "gcode_executed": False,
        "provider": status["provider"],
        "configured_provider": status["configured_provider"],
        "inventory_available": status["available"],
        "spoolman_connected": status["connected"],
        "local": {
            "available": local["available"],
            "active_slot": local["active_slot"],
            "stale": local["stale"],
            "presence_cached": local["presence_cached"],
        },
        "slots": slots,
        "error": error,
    }


def get_moonraker_status():
    status = inventory_status()
    runtime._set_inventory_state(status)
    if status["provider"] in {"none", "local"}:
        return {"spoolman_connected": False, "spool_id": None, "inventory_provider": status["provider"]}
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
            core.set_state(last_sync_reason="slot_not_confirmed", confirmation_values=confirmation_values)
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
        last_sync_result="local_inventory_active" if status["provider"] == "local" else "inventory_disabled",
        last_sync_reason=reason,
    )
    return False


def _send_manager(handler):
    with open(ui.MANAGER_HTML, "r", encoding="utf-8") as stream:
        text = stream.read()
    tags = (
        '<script defer src="/zmod-filaments-live.js"></script>',
        '<script defer src="/zmod-inventory-provider.js"></script>',
        '<script defer src="/zmod-combined-inventory.js"></script>',
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
        if path in {"/zmod-inventory-provider.js", "/zmod-combined-inventory.js"}:
            source = PROVIDER_UI_JS if path.endswith("provider.js") else COMBINED_UI_JS
            try:
                ui._send_static(self, source, "application/javascript; charset=utf-8")
            except FileNotFoundError:
                self.send_json(404, {"error": "Скрипт интерфейса не установлен"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        if path == "/api/printer/activity":
            self.send_json(200, printer_activity())
            return
        if path == "/api/inventory/combined":
            try:
                self.send_json(200, combined_inventory())
            except Exception as exc:
                self.send_json(500, {"error": str(exc), "gcode_executed": False})
            return
        if path == "/api/inventory/local":
            query = urllib.parse.parse_qs(parsed.query)
            force = query.get("refresh", [""])[0].lower() in {"1", "true", "yes"}
            try:
                self.send_json(200, local_inventory(force=force))
            except Exception as exc:
                core.event_log("error", "local_inventory_read_failed", "Не удалось сформировать локальный инвентарь", error=str(exc))
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
