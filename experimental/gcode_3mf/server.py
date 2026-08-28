#!/usr/bin/env python3
"""Experimental HTTP sidecar for sliced G-code 3MF on AD5X/Z-Mod.

This service is deliberately separate from the release IFS runtime. It exposes
read/prepare operations only; it never starts a print.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from inspect import ThreeMFError, inspect as inspect_3mf


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _within(root: Path, path: Path) -> bool:
    return path == root or root in path.parents


def _resolve_source(root: Path, value: str) -> Path:
    if not value:
        raise ApiError("missing filename")
    rel = Path(value)
    if rel.is_absolute():
        raise ApiError("filename must be relative to gcodes root")
    candidate = (root / rel).resolve()
    if not _within(root, candidate):
        raise ApiError("filename escapes gcodes root", 403)
    if not candidate.is_file():
        raise ApiError("file not found", 404)
    if not candidate.name.lower().endswith(".3mf"):
        raise ApiError("only .3mf containers are supported")
    return candidate


def _parse_plate(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        plate = int(value)
    except ValueError as exc:
        raise ApiError("plate must be an integer") from exc
    if plate < 1:
        raise ApiError("plate must be >= 1")
    return plate


def _read_json_body(handler: BaseHTTPRequestHandler, limit: int = 64 * 1024) -> Dict[str, Any]:
    raw_len = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_len)
    except ValueError as exc:
        raise ApiError("invalid Content-Length") from exc
    if length < 0 or length > limit:
        raise ApiError("request body too large", 413)
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ApiError(f"invalid JSON body: {exc}") from exc
    if not isinstance(data, dict):
        raise ApiError("JSON body must be an object")
    return data


def build_handler(gcodes_root: Path, cache_root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AD5X-GCode3MF-Experimental/0.1"

        def _send(self, status: int, payload: Dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.end_headers()
            self.wfile.write(data)

        def _error(self, exc: Exception) -> None:
            if isinstance(exc, ApiError):
                self._send(exc.status, {"ok": False, "error": str(exc)})
            elif isinstance(exc, ThreeMFError):
                self._send(422, {"ok": False, "error": str(exc)})
            else:
                self._send(500, {"ok": False, "error": str(exc)})

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(204, {})

        def do_GET(self) -> None:  # noqa: N802
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/api/health":
                    self._send(200, {
                        "ok": True,
                        "application": "AD5X G-code 3MF Experimental Sidecar",
                        "gcodes_root": str(gcodes_root),
                        "cache_root": str(cache_root),
                    })
                    return
                if parsed.path != "/api/inspect":
                    raise ApiError("not found", 404)
                qs = parse_qs(parsed.query)
                filename = qs.get("filename", [""])[0]
                plate = _parse_plate(qs.get("plate", [None])[0])
                source = _resolve_source(gcodes_root, filename)
                result = inspect_3mf(source, plate, None)
                result["source_relative"] = str(source.relative_to(gcodes_root))
                self._send(200, result)
            except Exception as exc:
                self._error(exc)

        def do_POST(self) -> None:  # noqa: N802
            try:
                parsed = urlparse(self.path)
                if parsed.path != "/api/prepare":
                    raise ApiError("not found", 404)
                body = _read_json_body(self)
                filename = str(body.get("filename", ""))
                plate = _parse_plate(str(body["plate"]) if body.get("plate") is not None else None)
                source = _resolve_source(gcodes_root, filename)
                result = inspect_3mf(source, plate, cache_root)
                if not result.get("sliced"):
                    raise ApiError("3MF is not a sliced G-code container", 422)
                cache_path = Path(str(result.get("cache_gcode", ""))).resolve()
                if not _within(gcodes_root, cache_path):
                    raise ApiError("prepared cache path escaped gcodes root", 500)
                result["source_relative"] = str(source.relative_to(gcodes_root))
                result["klipper_filename"] = str(cache_path.relative_to(gcodes_root))
                self._send(200, result)
            except Exception as exc:
                self._error(exc)

        def log_message(self, fmt: str, *args: object) -> None:
            print("[gcode_3mf] " + (fmt % args), flush=True)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental AD5X sliced 3MF HTTP sidecar")
    parser.add_argument("--host", default=os.environ.get("GCODE_3MF_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GCODE_3MF_PORT", "7914")))
    parser.add_argument("--gcodes-root", type=Path, default=Path(os.environ.get("GCODE_3MF_GCODES_ROOT", "/usr/data/gcodes")))
    parser.add_argument("--cache-root", type=Path, default=Path(os.environ.get("GCODE_3MF_CACHE_ROOT", "/usr/data/gcodes/.zmod/gcode_3mf")))
    args = parser.parse_args()

    gcodes_root = args.gcodes_root.resolve()
    cache_root = args.cache_root.resolve()
    if not gcodes_root.is_dir():
        raise SystemExit(f"gcodes root not found: {gcodes_root}")
    if not _within(gcodes_root, cache_root):
        raise SystemExit("cache root must be inside gcodes root")

    server = ThreadingHTTPServer((args.host, args.port), build_handler(gcodes_root, cache_root))
    print(f"AD5X G-code 3MF experimental sidecar listening on {args.host}:{args.port}", flush=True)
    print(f"gcodes_root={gcodes_root}", flush=True)
    print(f"cache_root={cache_root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
