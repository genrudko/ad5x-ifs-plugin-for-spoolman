#!/usr/bin/env python3
"""Phase B4 repair: expose local inventory without altering provider selection."""

import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.0-beta-repair1"
_BaseHandler = ui.UiRuntimeHandler


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


class LocalRuntimeHandler(_BaseHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/inventory/local":
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


runtime.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = LocalRuntimeHandler


if __name__ == "__main__":
    core.main()
