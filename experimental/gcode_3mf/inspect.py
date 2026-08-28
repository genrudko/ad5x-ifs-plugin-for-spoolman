#!/usr/bin/env python3
"""Experimental sliced G-code 3MF inspector/cache extractor.

Read-only by default.  With --extract-cache it writes only the selected
Metadata/plate_N.gcode into a caller-supplied cache directory using an atomic
replace after checksum validation.

This is intentionally self-contained (stdlib only) for AD5X/Z-Mod testing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

MAX_ENTRIES = 1024
MAX_GCODE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024

PLATE_GCODE_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode$")
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._ -]+")


class ThreeMFError(RuntimeError):
    pass


def _safe_archive_name(name: str) -> bool:
    # We never call ZipFile.extract(), but reject malformed/traversal names
    # anyway so validation has one clear security policy.
    if not name or "\\" in name or name.startswith("/"):
        return False
    parts = PurePosixPath(name).parts
    return all(part not in ("", ".", "..") for part in parts)


def _read_small(zf: zipfile.ZipFile, name: str, limit: int = 4 * 1024 * 1024) -> bytes:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return b""
    if info.file_size > limit:
        raise ThreeMFError(f"{name}: metadata member too large ({info.file_size} bytes)")
    return zf.read(info)


def _json_member(zf: zipfile.ZipFile, name: str) -> Any:
    raw = _read_small(zf, name)
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ThreeMFError(f"{name}: invalid JSON: {exc}") from exc


def _slice_info(zf: zipfile.ZipFile, plate: int) -> Dict[str, Any]:
    raw = _read_small(zf, "Metadata/slice_info.config")
    if not raw:
        return {}
    try:
        root = ET.fromstring(raw)
    except Exception as exc:
        raise ThreeMFError(f"Metadata/slice_info.config: invalid XML: {exc}") from exc

    header: Dict[str, str] = {}
    hdr = root.find("header")
    if hdr is not None:
        for item in hdr.findall("header_item"):
            key = item.get("key")
            if key:
                header[key] = item.get("value", "")

    selected = None
    for elem in root.findall("plate"):
        idx = None
        for md in elem.findall("metadata"):
            if md.get("key") == "index":
                try:
                    idx = int(md.get("value", ""))
                except ValueError:
                    idx = None
                break
        if idx == plate:
            selected = elem
            break
    if selected is None:
        return {"header": header, "plate": {}, "filaments": []}

    meta: Dict[str, str] = {}
    for md in selected.findall("metadata"):
        key = md.get("key")
        if key:
            meta[key] = md.get("value", "")

    filaments: List[Dict[str, Any]] = []
    for fil in selected.findall("filament"):
        item: Dict[str, Any] = dict(fil.attrib)
        try:
            item["id"] = int(item["id"])
        except (KeyError, ValueError):
            pass
        for key in ("used_m", "used_g", "nozzle_diameter"):
            if key in item:
                try:
                    item[key] = float(str(item[key]).replace(",", "."))
                except ValueError:
                    pass
        filaments.append(item)

    return {"header": header, "plate": meta, "filaments": filaments}


def _configured_filaments(project: Any) -> List[Dict[str, Any]]:
    if not isinstance(project, dict):
        return []
    fields = {
        "type": project.get("filament_type"),
        "name": project.get("filament_settings_id"),
        "color": project.get("filament_colour"),
        "vendor": project.get("filament_vendor"),
    }
    lengths = [len(v) for v in fields.values() if isinstance(v, list)]
    count = max(lengths, default=0)
    result: List[Dict[str, Any]] = []
    for idx in range(count):
        item: Dict[str, Any] = {"index0": idx, "id1": idx + 1}
        for out_key, values in fields.items():
            if isinstance(values, list) and idx < len(values):
                item[out_key] = values[idx]
        result.append(item)
    return result


def _stream_md5(zf: zipfile.ZipFile, name: str, sink=None) -> Tuple[str, int]:
    digest = hashlib.md5()
    total = 0
    with zf.open(name, "r") as src:
        while True:
            chunk = src.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_GCODE_BYTES:
                raise ThreeMFError(f"{name}: G-code exceeds {MAX_GCODE_BYTES} bytes")
            digest.update(chunk)
            if sink is not None:
                sink.write(chunk)
    return digest.hexdigest(), total


def _expected_md5(zf: zipfile.ZipFile, gcode_name: str) -> Optional[str]:
    raw = _read_small(zf, gcode_name + ".md5", limit=1024)
    if not raw:
        return None
    value = raw.decode("ascii", "ignore").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ThreeMFError(f"{gcode_name}.md5: invalid MD5 value")
    return value


def _cache_filename(source: Path, plate: int, digest: str) -> str:
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


def inspect(path: Path, plate: Optional[int], extract_cache: Optional[Path]) -> Dict[str, Any]:
    if not path.is_file():
        raise ThreeMFError(f"file not found: {path}")
    if not zipfile.is_zipfile(path):
        raise ThreeMFError("not a ZIP/3MF container")

    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise ThreeMFError(f"too many ZIP entries: {len(infos)} > {MAX_ENTRIES}")
        total_uncompressed = sum(i.file_size for i in infos)
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            raise ThreeMFError("ZIP uncompressed size exceeds safety limit")
        bad = [i.filename for i in infos if not _safe_archive_name(i.filename)]
        if bad:
            raise ThreeMFError(f"unsafe ZIP member name: {bad[0]!r}")

        plates: List[int] = []
        gcode_by_plate: Dict[int, str] = {}
        for info in infos:
            m = PLATE_GCODE_RE.match(info.filename)
            if m:
                pnum = int(m.group(1))
                if pnum in gcode_by_plate:
                    raise ThreeMFError(f"duplicate G-code member for plate {pnum}")
                if info.file_size <= 0:
                    raise ThreeMFError(f"{info.filename}: empty G-code")
                if info.file_size > MAX_GCODE_BYTES:
                    raise ThreeMFError(f"{info.filename}: G-code too large")
                plates.append(pnum)
                gcode_by_plate[pnum] = info.filename
        plates.sort()

        if not plates:
            return {
                "ok": True,
                "sliced": False,
                "source": str(path),
                "reason": "no Metadata/plate_N.gcode member",
                "plates": [],
            }

        selected = plate if plate is not None else plates[0]
        if selected not in gcode_by_plate:
            raise ThreeMFError(f"plate {selected} not found; available: {plates}")

        gcode_name = gcode_by_plate[selected]
        expected = _expected_md5(zf, gcode_name)

        cache_path: Optional[Path] = None
        if extract_cache is None:
            actual, gcode_size = _stream_md5(zf, gcode_name)
        else:
            extract_cache.mkdir(parents=True, exist_ok=True)
            if not extract_cache.is_dir():
                raise ThreeMFError(f"cache path is not a directory: {extract_cache}")
            fd, tmp_name = tempfile.mkstemp(prefix=".gcode3mf-", suffix=".tmp", dir=str(extract_cache))
            try:
                with os.fdopen(fd, "wb") as out:
                    actual, gcode_size = _stream_md5(zf, gcode_name, sink=out)
                    out.flush()
                    os.fsync(out.fileno())
                if expected is not None and actual != expected:
                    raise ThreeMFError(
                        f"MD5 mismatch for {gcode_name}: expected {expected}, got {actual}"
                    )
                cache_path = extract_cache / _cache_filename(path, selected, actual)
                os.replace(tmp_name, cache_path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

        if expected is not None and actual != expected:
            raise ThreeMFError(
                f"MD5 mismatch for {gcode_name}: expected {expected}, got {actual}"
            )

        slice_data = _slice_info(zf, selected)
        plate_json = _json_member(zf, f"Metadata/plate_{selected}.json")
        project = _json_member(zf, "Metadata/project_settings.config")
        sequence = _json_member(zf, "Metadata/filament_sequence.json")

        configured = _configured_filaments(project)
        by_id1 = {item["id1"]: item for item in configured}
        used: List[Dict[str, Any]] = []
        for item in slice_data.get("filaments", []):
            merged = dict(item)
            fid = item.get("id")
            if isinstance(fid, int) and fid in by_id1:
                merged["configured"] = by_id1[fid]
            used.append(merged)

        names = set(zf.namelist())
        return {
            "ok": True,
            "sliced": True,
            "source": str(path),
            "plates": plates,
            "selected_plate": selected,
            "gcode_member": gcode_name,
            "gcode_size": gcode_size,
            "gcode_md5": actual,
            "gcode_md5_expected": expected,
            "gcode_md5_valid": expected is None or actual == expected,
            "preview_members": [
                name for name in (
                    f"Metadata/plate_{selected}.png",
                    f"Metadata/plate_{selected}_small.png",
                    f"Metadata/plate_no_light_{selected}.png",
                )
                if name in names
            ],
            "slice_info": slice_data,
            "plate_json": plate_json,
            "filament_sequence": sequence,
            "configured_filaments": configured,
            "used_filaments": used,
            "cache_gcode": str(cache_path) if cache_path is not None else None,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a sliced G-code 3MF; optionally extract selected plate to hidden cache"
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--plate", type=int, default=None)
    parser.add_argument("--extract-cache", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    try:
        result = inspect(args.file, args.plate, args.extract_cache)
    except ThreeMFError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    except (OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 3

    if args.compact:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
