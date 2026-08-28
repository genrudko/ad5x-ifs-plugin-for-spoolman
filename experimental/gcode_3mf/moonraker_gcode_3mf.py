#!/usr/bin/env python3
"""Experimental Moonraker component for direct .gcode.3mf print starts.

This component deliberately does not modify Moonraker core files.  When loaded
as [gcode_3mf], it wraps the already-registered klippy_apis.start_print method.
Normal G-code paths are passed through unchanged.  A sliced 3MF is validated,
its single embedded plate G-code is atomically extracted into a hidden .zmod
cache, optional IFS preflight is consulted, and the original Moonraker start
method is called with the hidden G-code filename.

The default dry_run=True is intentionally fail-closed for hardware testing: a
valid request is intercepted and prepared but an HTTP error is returned before
Klipper is asked to print.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.parse
import urllib.request
import zipfile
from typing import Any, Dict, Optional, Tuple

PLATE_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode$")
MAX_ENTRIES = 1024
MAX_GCODE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._ -]+")


class GCode3MF:
    def __init__(self, config):
        self.server = config.get_server()
        self.klippy_apis = self.server.lookup_component("klippy_apis")
        self.file_manager = self.server.lookup_component("file_manager")
        self.dry_run = config.getboolean("dry_run", True)
        self.block_on_ifs_mismatch = config.getboolean(
            "block_on_ifs_mismatch", True
        )
        self.ifs_preflight_url = config.get(
            "ifs_preflight_url", "http://127.0.0.1:7913"
        ).rstrip("/")
        self.cache_subdir = config.get(
            "cache_subdir", ".zmod/gcode_3mf"
        ).strip("/")

        original = self.klippy_apis.start_print
        if getattr(original, "_gcode_3mf_wrapped", False):
            raise self.server.error("gcode_3mf start interceptor already installed")
        self._original_start_print = original

        async def wrapped_start_print(
            filename: str,
            wait_klippy_started: bool = False,
            user=None,
        ):
            return await self._start_print(
                filename,
                wait_klippy_started=wait_klippy_started,
                user=user,
            )

        wrapped_start_print._gcode_3mf_wrapped = True
        self.klippy_apis.start_print = wrapped_start_print
        logging.info(
            "GCode3MF experimental start interceptor installed "
            "(dry_run=%s, block_on_ifs_mismatch=%s)",
            self.dry_run,
            self.block_on_ifs_mismatch,
        )

    def _gcodes_root(self) -> Path:
        value = self.file_manager.get_directory("gcodes")
        if not value:
            raise RuntimeError("Moonraker gcodes root is unavailable")
        return Path(value).resolve()

    @staticmethod
    def _within(root: Path, path: Path) -> bool:
        return path == root or root in path.parents

    def _resolve_source(self, filename: str) -> Tuple[Path, str]:
        rel_text = str(filename or "").lstrip("/")
        rel = Path(rel_text)
        if not rel_text or rel.is_absolute():
            raise ValueError("invalid 3MF filename")
        root = self._gcodes_root()
        source = (root / rel).resolve()
        if not self._within(root, source):
            raise ValueError("3MF filename escapes gcodes root")
        if not source.is_file():
            raise FileNotFoundError(rel_text)
        if not source.name.lower().endswith(".3mf"):
            raise ValueError("not a 3MF file")
        return source, rel_text

    @staticmethod
    def _safe_archive_name(name: str) -> bool:
        if not name or "\\" in name or name.startswith("/"):
            return False
        parts = PurePosixPath(name).parts
        return all(part not in ("", ".", "..") for part in parts)

    @staticmethod
    def _expected_md5(zf: zipfile.ZipFile, member: str) -> Optional[str]:
        md5_name = member + ".md5"
        try:
            info = zf.getinfo(md5_name)
        except KeyError:
            return None
        if info.file_size <= 0 or info.file_size > 1024:
            raise ValueError("invalid embedded MD5 member")
        value = zf.read(info).decode("ascii", "ignore").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{32}", value):
            raise ValueError("invalid embedded MD5 value")
        return value

    @staticmethod
    def _cache_name(source: Path, plate: int, digest: str) -> str:
        name = source.name
        lower = name.lower()
        if lower.endswith(".gcode.3mf"):
            stem = name[:-10]
        elif lower.endswith(".3mf"):
            stem = name[:-4]
        else:
            stem = source.stem
        stem = SAFE_STEM_RE.sub("_", stem).strip(" ._") or "plate"
        return f"{stem}-p{plate}-{digest[:12]}.gcode"

    def _prepare_sync(self, filename: str) -> Dict[str, Any]:
        source, source_relative = self._resolve_source(filename)
        root = self._gcodes_root()
        cache_root = (root / self.cache_subdir).resolve()
        if not self._within(root, cache_root):
            raise ValueError("cache path escapes gcodes root")
        cache_root.mkdir(parents=True, exist_ok=True)

        if not zipfile.is_zipfile(source):
            raise ValueError("not a ZIP/3MF container")

        with zipfile.ZipFile(source, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ValueError("too many ZIP entries")
            if sum(item.file_size for item in infos) > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("ZIP uncompressed size exceeds safety limit")
            for item in infos:
                if not self._safe_archive_name(item.filename):
                    raise ValueError(f"unsafe ZIP member name: {item.filename!r}")

            plates: Dict[int, str] = {}
            for item in infos:
                match = PLATE_RE.match(item.filename)
                if not match:
                    continue
                plate = int(match.group(1))
                if plate in plates:
                    raise ValueError(f"duplicate G-code member for plate {plate}")
                if item.file_size <= 0 or item.file_size > MAX_GCODE_BYTES:
                    raise ValueError(f"invalid G-code size for plate {plate}")
                plates[plate] = item.filename

            if not plates:
                raise ValueError("3MF is not a sliced G-code container")
            if len(plates) != 1:
                raise ValueError(
                    "multi-plate 3MF direct start is not enabled yet; "
                    "select a plate from the 7913 UI"
                )

            plate = next(iter(sorted(plates)))
            member = plates[plate]
            expected = self._expected_md5(zf, member)
            digest = hashlib.md5()
            total = 0
            fd, tmp_name = tempfile.mkstemp(
                prefix=".gcode3mf-", suffix=".tmp", dir=str(cache_root)
            )
            try:
                with os.fdopen(fd, "wb") as out, zf.open(member, "r") as src:
                    while True:
                        chunk = src.read(CHUNK)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_GCODE_BYTES:
                            raise ValueError("embedded G-code exceeds safety limit")
                        digest.update(chunk)
                        out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())

                actual = digest.hexdigest()
                if expected is not None and actual != expected:
                    raise ValueError(
                        f"embedded G-code MD5 mismatch: expected {expected}, got {actual}"
                    )
                cache_path = cache_root / self._cache_name(source, plate, actual)
                os.replace(tmp_name, cache_path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

        return {
            "source_relative": source_relative,
            "plate": plate,
            "member": member,
            "gcode_size": total,
            "gcode_md5": actual,
            "md5_expected": expected,
            "md5_valid": expected is None or actual == expected,
            "cache_relative": str(cache_path.relative_to(root)),
        }

    def _preflight_sync(self, source_relative: str) -> Dict[str, Any]:
        url = (
            self.ifs_preflight_url
            + "/api/3mf/preflight?filename="
            + urllib.parse.quote(source_relative, safe="/")
        )
        try:
            with urllib.request.urlopen(url, timeout=3.0) as response:
                raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            preflight = data.get("preflight") if isinstance(data, dict) else None
            if not isinstance(preflight, dict):
                raise ValueError("invalid IFS preflight response")
            return {
                "available": True,
                "preflight": preflight,
            }
        except Exception as exc:
            # Base 3MF printing must remain independent of the optional IFS UI.
            return {
                "available": False,
                "error": str(exc),
                "preflight": None,
            }

    @staticmethod
    def _preflight_summary(preflight: Dict[str, Any]) -> str:
        summary = preflight.get("summary") or {}
        parts = []
        for key in (
            "exact",
            "material_only",
            "unassigned",
            "material_mismatch",
            "unmapped",
            "missing",
            "low_weight",
        ):
            value = summary.get(key)
            if value:
                parts.append(f"{key}={value}")
        return ", ".join(parts) or "no warnings"

    async def _start_print(
        self,
        filename: str,
        wait_klippy_started: bool = False,
        user=None,
    ):
        if not str(filename).lower().endswith(".3mf"):
            return await self._original_start_print(
                filename,
                wait_klippy_started=wait_klippy_started,
                user=user,
            )

        loop = asyncio.get_running_loop()
        try:
            prepared = await loop.run_in_executor(
                None, self._prepare_sync, filename
            )
            ifs_result = await loop.run_in_executor(
                None, self._preflight_sync, prepared["source_relative"]
            )
        except Exception as exc:
            logging.exception("GCode3MF preparation failed for %s", filename)
            raise self.server.error(f"GCode3MF: {exc}", 422)

        preflight = ifs_result.get("preflight")
        if (
            self.block_on_ifs_mismatch
            and isinstance(preflight, dict)
            and preflight.get("requires_override") is True
        ):
            summary = self._preflight_summary(preflight)
            logging.warning(
                "GCode3MF direct start blocked by IFS preflight: %s (%s)",
                prepared["source_relative"],
                summary,
            )
            raise self.server.error(
                "GCode3MF: IFS preflight requires confirmation "
                f"({summary}). Open http://PRINTER_IP:7913/ to review/override.",
                409,
            )

        logging.info(
            "GCode3MF prepared source=%s plate=%s hidden=%s md5=%s "
            "ifs_available=%s",
            prepared["source_relative"],
            prepared["plate"],
            prepared["cache_relative"],
            prepared["gcode_md5"],
            ifs_result.get("available"),
        )

        if self.dry_run:
            raise self.server.error(
                "GCode3MF DRY RUN OK: validated and prepared "
                f"{prepared['source_relative']} -> {prepared['cache_relative']}; "
                "Klipper was NOT started.",
                409,
            )

        return await self._original_start_print(
            prepared["cache_relative"],
            wait_klippy_started=wait_klippy_started,
            user=user,
        )


def load_component(config):
    return GCode3MF(config)
