#!/usr/bin/env python3
"""Temporary combined IFS + sliced 3MF test host on port 7913.

This file intentionally imports the installed release IFS runtime instead of
modifying it.  It replaces only the HTTP handler at runtime, adding a tabbed
root page and /api/3mf/* endpoints.  The normal IFS API and monitor remain the
release implementation.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
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
        server_version = "AD5X-IFS-3MF-Experimental/0.1"

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
                        "version": "0.1",
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

                if parsed.path == "/api/3mf/inspect":
                    source = resolve_source(filename)
                    result = inspector.inspect(source, plate, None)
                    result["source_relative"] = str(source.relative_to(GCODES_ROOT))
                    self.send_3mf_json(200, result)
                    return
            except Exception as exc:
                self.fail_3mf(exc)
                return

            super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/3mf/prepare":
                return super().do_POST()
            try:
                body = read_json_body(self)
                filename = str(body.get("filename", ""))
                plate = parse_plate(body.get("plate"))
                source = resolve_source(filename)
                result = inspector.inspect(source, plate, CACHE_ROOT)
                if not result.get("sliced"):
                    raise ValueError("3MF is not a sliced G-code container")
                cache_path = Path(str(result.get("cache_gcode", ""))).resolve()
                if not within(GCODES_ROOT, cache_path):
                    raise ValueError("cache path escaped gcodes root")
                result["source_relative"] = str(source.relative_to(GCODES_ROOT))
                result["klipper_filename"] = str(cache_path.relative_to(GCODES_ROOT))
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
