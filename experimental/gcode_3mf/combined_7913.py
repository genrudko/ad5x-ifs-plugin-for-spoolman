#!/usr/bin/env python3
"""Temporary combined IFS + sliced 3MF test host on port 7913.

This file intentionally imports the installed release IFS runtime instead of
modifying it. It replaces only the HTTP handler at runtime, adding a tabbed
root page and /api/3mf/* endpoints. The normal IFS API and monitor remain the
release implementation.

The 3MF print path is deliberately explicit: validate/extract the selected
plate into the hidden .zmod cache, optionally report IFS/Spoolman compatibility,
then ask Moonraker to print the hidden G-code. No IFS assignments are modified.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import zipfile
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
GCODES_ROOT = Path(os.environ.get("GCODE_3MF_GCODES_ROOT", "/usr/data/gcodes")).resolve()
CACHE_ROOT = Path(os.environ.get("GCODE_3MF_CACHE_ROOT", "/usr/data/gcodes/.zmod/gcode_3mf")).resolve()
COMBINED_HTML = HERE / "combined.html"
INSPECTOR = HERE / "inspect.py"

IFS_CANDIDATES = [
    Path("/opt/config/mod_data/ifs_spoolman/ifs_spoolman.py"),
    Path("/root/printer_data/config/mod_data/ifs_spoolman/ifs_spoolman.py"),
    Path("/usr/data/config/mod_data/ifs_spoolman/ifs_spoolman.py"),
]


def load_file_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def find_ifs_runtime() -> Path:
    for path in IFS_CANDIDATES:
        if path.is_file():
            return path.resolve()
    raise RuntimeError("installed IFS runtime not found")


def within(root: Path, path: Path) -> bool:
    return path == root or root in path.parents


def resolve_source(value: str) -> Path:
    if not value:
        raise ValueError("missing filename")
    rel = Path(value)
    if rel.is_absolute():
        raise ValueError("filename must be relative")
    source = (GCODES_ROOT / rel).resolve()
    if not within(GCODES_ROOT, source):
        raise ValueError("filename escapes gcodes root")
    if not source.is_file():
        raise FileNotFoundError(value)
    if not source.name.lower().endswith(".3mf"):
        raise ValueError("only .3mf is supported")
    return source


def parse_plate(value):
    if value in (None, ""):
        return None
    plate = int(value)
    if plate < 1:
        raise ValueError("plate must be >= 1")
    return plate


def list_3mf_files():
    result = []
    for path in sorted(GCODES_ROOT.rglob("*.3mf"), key=lambda p: str(p).lower()):
        if not path.is_file():
            continue
        rel = path.relative_to(GCODES_ROOT)
        if ".zmod" in rel.parts:
            continue
        stat = path.stat()
        result.append({"filename": str(rel), "size": stat.st_size, "modified": stat.st_mtime})
        if len(result) >= 500:
            break
    return result


def read_preview(source: Path, plate: int, size: str) -> bytes:
    candidates = (
        [f"Metadata/plate_{plate}_small.png", f"Metadata/plate_{plate}.png"]
        if size == "small"
        else [f"Metadata/plate_{plate}.png", f"Metadata/plate_{plate}_small.png"]
    )
    with zipfile.ZipFile(source, "r") as zf:
        names = set(zf.namelist())
        for name in candidates:
            if name not in names:
                continue
            info = zf.getinfo(name)
            if info.file_size <= 0 or info.file_size > 16 * 1024 * 1024:
                raise ValueError("invalid preview size")
            return zf.read(info)
    raise FileNotFoundError("preview not found")


def read_json_body(handler, limit=65536):
    length = int(handler.headers.get("Content-Length", "0"))
    if length < 0 or length > limit:
        raise ValueError("request body too large")
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def normalize_material(value):
    text = str(value or "").strip().upper()
    return text or None


def normalize_color(value):
    text = str(value or "").strip().lstrip("#").upper()
    if len(text) >= 6 and all(ch in "0123456789ABCDEF" for ch in text[:6]):
        return "#" + text[:6]
    return None


def filament_requirement(item):
    configured = item.get("configured") if isinstance(item, dict) else None
    configured = configured if isinstance(configured, dict) else {}
    material = normalize_material(item.get("type") or configured.get("type"))
    color = normalize_color(item.get("color") or configured.get("color"))
    try:
        used_g = float(item.get("used_g"))
    except (TypeError, ValueError):
        used_g = None
    return {
        "id": item.get("id"),
        "material": material,
        "color": color,
        "used_g": used_g,
    }


def assigned_slots(ifs):
    with ifs.lock:
        assignments = dict(ifs.assignments)
        status = dict(ifs.state)
    spools = ifs.list_spools()
    spool_by_id = {}
    for spool in spools if isinstance(spools, list) else []:
        if not isinstance(spool, dict):
            continue
        try:
            spool_by_id[int(spool.get("id"))] = spool
        except (TypeError, ValueError):
            continue

    slots = []
    for slot in range(1, 5):
        raw_id = assignments.get(str(slot))
        try:
            spool_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            spool_id = None
        spool = spool_by_id.get(spool_id)
        filament = spool.get("filament") if isinstance(spool, dict) else None
        filament = filament if isinstance(filament, dict) else {}
        vendor = filament.get("vendor")
        if isinstance(vendor, dict):
            vendor = vendor.get("name")
        try:
            remaining = float(spool.get("remaining_weight")) if spool is not None else None
        except (TypeError, ValueError):
            remaining = None
        slots.append({
            "slot": slot,
            "active": status.get("active_slot") == slot,
            "spool_id": spool_id,
            "material": normalize_material(filament.get("material")),
            "color": normalize_color(filament.get("color_hex")),
            "name": filament.get("name"),
            "vendor": vendor,
            "remaining_g": remaining,
        })
    return slots, status


def build_preflight(ifs, inspection):
    requirements = [filament_requirement(item) for item in inspection.get("used_filaments", [])]
    try:
        slots, status = assigned_slots(ifs)
    except Exception as exc:
        return {
            "available": False,
            "optional": True,
            "error": str(exc),
            "requirements": requirements,
            "matches": [],
            "summary": {"exact": 0, "material_only": 0, "missing": len(requirements), "low_weight": 0},
        }

    remaining_slots = {item["slot"]: item for item in slots if item.get("spool_id") is not None}
    matches = []
    summary = {"exact": 0, "material_only": 0, "missing": 0, "low_weight": 0}

    # Most constrained requirements first, while retaining output ordering later.
    work = []
    for index, req in enumerate(requirements):
        exact = []
        material_only = []
        for slot in remaining_slots.values():
            if not req["material"] or slot["material"] != req["material"]:
                continue
            if req["color"] and slot["color"] and req["color"] == slot["color"]:
                exact.append(slot["slot"])
            else:
                material_only.append(slot["slot"])
        work.append((len(exact), len(exact) + len(material_only), index, req))
    work.sort(key=lambda row: (row[0] == 0, row[0] + row[1], row[2]))

    mapped = {}
    for _, _, index, req in work:
        exact = []
        material_only = []
        for slot in remaining_slots.values():
            if not req["material"] or slot["material"] != req["material"]:
                continue
            if req["color"] and slot["color"] and req["color"] == slot["color"]:
                exact.append(slot)
            else:
                material_only.append(slot)
        candidates = exact or material_only
        if candidates:
            candidates.sort(key=lambda item: (not item.get("active", False), item["slot"]))
            slot = candidates[0]
            remaining_slots.pop(slot["slot"], None)
            quality = "exact" if exact else "material_only"
            weight_ok = None
            if req["used_g"] is not None and slot["remaining_g"] is not None:
                weight_ok = slot["remaining_g"] >= req["used_g"]
                if not weight_ok:
                    summary["low_weight"] += 1
            summary[quality] += 1
            mapped[index] = {"requirement": req, "match": quality, "slot": slot, "weight_ok": weight_ok}
        else:
            summary["missing"] += 1
            mapped[index] = {"requirement": req, "match": "missing", "slot": None, "weight_ok": None}

    for index in range(len(requirements)):
        matches.append(mapped[index])

    return {
        "available": True,
        "optional": True,
        "spoolman_connected": bool(status.get("spoolman_connected")),
        "active_slot": status.get("active_slot"),
        "requirements": requirements,
        "slots": slots,
        "matches": matches,
        "summary": summary,
    }


def moonraker_request(base, path, method="GET", timeout=15):
    url = base.rstrip("/") + path
    data = b"" if method == "POST" else None
    request = urllib.request.Request(url, data=data, headers={"Accept": "application/json"}, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def printer_busy(ifs):
    payload = moonraker_request(ifs.MOONRAKER, "/printer/objects/query?virtual_sdcard&print_stats")
    status = payload.get("result", {}).get("status", {}) if isinstance(payload, dict) else {}
    vsd = status.get("virtual_sdcard", {}) if isinstance(status, dict) else {}
    stats = status.get("print_stats", {}) if isinstance(status, dict) else {}
    state = str(stats.get("state") or "").lower()
    active = bool(vsd.get("is_active"))
    return active or state in ("printing", "paused"), {"virtual_sdcard": vsd, "print_stats": stats}


def prepare_container(inspector, source, plate):
    result = inspector.inspect(source, plate, CACHE_ROOT)
    if not result.get("sliced"):
        raise ValueError("3MF is not a sliced G-code container")
    if result.get("gcode_md5_valid") is not True:
        raise ValueError("embedded G-code checksum validation failed")
    cache_path = Path(str(result.get("cache_gcode", ""))).resolve()
    if not within(GCODES_ROOT, cache_path):
        raise ValueError("cache path escaped gcodes root")
    result["source_relative"] = str(source.relative_to(GCODES_ROOT))
    result["klipper_filename"] = str(cache_path.relative_to(GCODES_ROOT))
    return result


def main():
    if not GCODES_ROOT.is_dir():
        raise SystemExit(f"gcodes root not found: {GCODES_ROOT}")
    if not within(GCODES_ROOT, CACHE_ROOT):
        raise SystemExit("cache root must be inside gcodes root")
    if not COMBINED_HTML.is_file():
        raise SystemExit(f"combined UI not found: {COMBINED_HTML}")
    if not INSPECTOR.is_file():
        raise SystemExit(f"inspector not found: {INSPECTOR}")

    ifs = load_file_module("ad5x_ifs_release_runtime", find_ifs_runtime())
    inspector = load_file_module("ad5x_gcode3mf_inspector", INSPECTOR)
    OriginalHandler = ifs.Handler

    class CombinedHandler(OriginalHandler):
        server_version = "AD5X-IFS-3MF-Experimental/0.2"

        def send_bytes(self, status, data, content_type, cache_control="no-store"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def send_3mf_json(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_bytes(status, data, "application/json; charset=utf-8")

        def fail_3mf(self, exc):
            status = 404 if isinstance(exc, FileNotFoundError) else 422
            self.send_3mf_json(status, {"ok": False, "error": str(exc)})

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self.send_bytes(200, COMBINED_HTML.read_bytes(), "text/html; charset=utf-8")
                    return
                if parsed.path == "/ifs":
                    self.send_bytes(200, ifs.HTML.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if parsed.path == "/api/3mf/health":
                    self.send_3mf_json(200, {
                        "ok": True,
                        "application": "AD5X IFS + G-code 3MF Experimental",
                        "version": "0.2",
                        "ifs_version": getattr(ifs, "APP_VERSION", None),
                    })
                    return
                if parsed.path == "/api/3mf/files":
                    self.send_3mf_json(200, {"ok": True, "files": list_3mf_files()})
                    return

                qs = parse_qs(parsed.query)
                filename = qs.get("filename", [""])[0]
                plate = parse_plate(qs.get("plate", [None])[0])

                if parsed.path == "/api/3mf/preview":
                    source = resolve_source(filename)
                    size = qs.get("size", ["large"])[0]
                    if size not in ("small", "large"):
                        raise ValueError("size must be small or large")
                    data = read_preview(source, plate or 1, size)
                    self.send_bytes(200, data, "image/png", "private, max-age=60")
                    return

                if parsed.path in ("/api/3mf/inspect", "/api/3mf/preflight"):
                    source = resolve_source(filename)
                    result = inspector.inspect(source, plate, None)
                    result["source_relative"] = str(source.relative_to(GCODES_ROOT))
                    if parsed.path == "/api/3mf/preflight":
                        self.send_3mf_json(200, {
                            "ok": True,
                            "source_relative": result["source_relative"],
                            "preflight": build_preflight(ifs, result),
                        })
                    else:
                        self.send_3mf_json(200, result)
                    return
            except Exception as exc:
                self.fail_3mf(exc)
                return

            super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path not in ("/api/3mf/prepare", "/api/3mf/start"):
                return super().do_POST()
            try:
                body = read_json_body(self)
                filename = str(body.get("filename", ""))
                plate = parse_plate(body.get("plate"))
                source = resolve_source(filename)

                if parsed.path == "/api/3mf/start":
                    busy, printer_state = printer_busy(ifs)
                    if busy:
                        raise ValueError("printer is already printing or paused")

                result = prepare_container(inspector, source, plate)
                preflight = build_preflight(ifs, result)

                if parsed.path == "/api/3mf/start":
                    encoded = urllib.parse.quote(result["klipper_filename"], safe="/")
                    start_result = moonraker_request(
                        ifs.MOONRAKER,
                        "/printer/print/start?filename=" + encoded,
                        method="POST",
                        timeout=30,
                    )
                    self.send_3mf_json(200, {
                        "ok": True,
                        "started": True,
                        "source_relative": result["source_relative"],
                        "klipper_filename": result["klipper_filename"],
                        "gcode_md5": result.get("gcode_md5"),
                        "preflight": preflight,
                        "printer_before": printer_state,
                        "moonraker": start_result,
                    })
                    return

                result["preflight"] = preflight
                self.send_3mf_json(200, result)
            except Exception as exc:
                self.fail_3mf(exc)

    ifs.Handler = CombinedHandler
    print("AD5X IFS + G-code 3MF temporary host on release IFS port", ifs.PORT, flush=True)
    print("release runtime:", find_ifs_runtime(), flush=True)
    print("gcodes_root:", GCODES_ROOT, flush=True)
    ifs.main()


if __name__ == "__main__":
    main()
