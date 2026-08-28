#!/usr/bin/env python3
"""Slot-aware wrapper for the experimental combined IFS + sliced 3MF host.

The base v0.2 host treated IFS assignments as a pool and could match a sliced
filament to any compatible slot. That is wrong for AD5X sliced G-code: filament
IDs are tool/slot identities (id 1 -> T0 -> IFS 1, etc.). This wrapper replaces
only the preflight policy and UI, leaving the release IFS runtime untouched.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE_HOST = HERE / "combined_7913.py"
V03_HTML = HERE / "combined_v03.html"


def load_base():
    spec = importlib.util.spec_from_file_location("ad5x_ifs_3mf_v02", str(BASE_HOST))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base host: {BASE_HOST}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def slot_aware_preflight(base, ifs, inspection):
    requirements = [
        base.filament_requirement(item)
        for item in inspection.get("used_filaments", [])
    ]

    try:
        slots, status = base.assigned_slots(ifs)
    except Exception as exc:
        return {
            "available": False,
            "optional": True,
            "mapping_mode": "fixed_slot_by_filament_id",
            "error": str(exc),
            "requirements": requirements,
            "matches": [],
            "summary": {
                "exact": 0,
                "material_only": 0,
                "unassigned": 0,
                "material_mismatch": 0,
                "unmapped": len(requirements),
                "missing": len(requirements),
                "low_weight": 0,
                "elsewhere": 0,
            },
            "safe_to_print": None,
            "requires_override": False,
        }

    by_slot = {item["slot"]: item for item in slots}
    matches = []
    summary = {
        "exact": 0,
        "material_only": 0,
        "unassigned": 0,
        "material_mismatch": 0,
        "unmapped": 0,
        "missing": 0,
        "low_weight": 0,
        "elsewhere": 0,
    }
    warnings = []

    plate_meta = inspection.get("slice_info", {}).get("plate", {})
    dynamic_map = str(plate_meta.get("enable_filament_dynamic_map", "")).strip().lower()
    if dynamic_map in ("1", "true", "yes", "on"):
        warnings.append("slicer metadata enables dynamic filament mapping; fixed-slot preflight is not authoritative")

    req_ids = []
    for req in requirements:
        rid = as_int(req.get("id"))
        if rid is not None:
            req_ids.append(rid)

    plate_json = inspection.get("plate_json")
    if isinstance(plate_json, dict) and isinstance(plate_json.get("filament_ids"), list):
        zero_based = [as_int(v) for v in plate_json.get("filament_ids", [])]
        plate_slots = sorted({v + 1 for v in zero_based if v is not None and 0 <= v < 4})
        if plate_slots and sorted(set(req_ids)) != plate_slots:
            warnings.append(
                f"plate_json filament_ids imply IFS slots {plate_slots}, while slice_info uses {sorted(set(req_ids))}"
            )

    sequence = inspection.get("filament_sequence")
    selected_plate = inspection.get("selected_plate")
    if isinstance(sequence, dict):
        plate_seq = sequence.get(f"plate_{selected_plate}")
        if isinstance(plate_seq, dict) and isinstance(plate_seq.get("sequence"), list):
            seq_ids = sorted({v for v in (as_int(x) for x in plate_seq.get("sequence", [])) if v is not None})
            if seq_ids and not set(seq_ids).issubset(set(req_ids)):
                warnings.append(
                    f"filament_sequence references IDs {seq_ids}, outside used filament IDs {sorted(set(req_ids))}"
                )

    for req in requirements:
        target_slot = as_int(req.get("id"))
        target = by_slot.get(target_slot) if target_slot in (1, 2, 3, 4) else None
        elsewhere = []

        for slot in slots:
            if slot.get("slot") == target_slot or slot.get("spool_id") is None:
                continue
            if not req.get("material") or slot.get("material") != req.get("material"):
                continue
            quality = (
                "exact"
                if req.get("color") and slot.get("color") and req.get("color") == slot.get("color")
                else "material_only"
            )
            elsewhere.append({"quality": quality, "slot": slot})

        elsewhere.sort(key=lambda item: (item["quality"] != "exact", item["slot"]["slot"]))
        if elsewhere:
            summary["elsewhere"] += 1

        weight_ok = None
        if target_slot not in (1, 2, 3, 4):
            match = "unmapped"
            summary["unmapped"] += 1
            summary["missing"] += 1
        elif target is None or target.get("spool_id") is None:
            match = "unassigned"
            summary["unassigned"] += 1
            summary["missing"] += 1
        elif not req.get("material") or target.get("material") != req.get("material"):
            match = "material_mismatch"
            summary["material_mismatch"] += 1
            summary["missing"] += 1
        else:
            if req.get("color") and target.get("color") and req.get("color") == target.get("color"):
                match = "exact"
            else:
                match = "material_only"
            summary[match] += 1

            if req.get("used_g") is not None and target.get("remaining_g") is not None:
                weight_ok = target.get("remaining_g") >= req.get("used_g")
                if not weight_ok:
                    summary["low_weight"] += 1

        matches.append({
            "requirement": req,
            "target_slot": target_slot,
            "tool": f"T{target_slot - 1}" if target_slot in (1, 2, 3, 4) else None,
            "match": match,
            "slot": target,
            "weight_ok": weight_ok,
            "compatible_elsewhere": elsewhere,
        })

    safe = (
        not warnings
        and summary["missing"] == 0
        and summary["low_weight"] == 0
    )

    return {
        "available": True,
        "optional": True,
        "mapping_mode": "fixed_slot_by_filament_id",
        "mapping_note": "sliced filament id N is checked against IFS slot N (G-code tool T(N-1)); compatible material in another slot is only a hint, never a match",
        "spoolman_connected": bool(status.get("spoolman_connected")),
        "active_slot": status.get("active_slot"),
        "requirements": requirements,
        "slots": slots,
        "matches": matches,
        "summary": summary,
        "warnings": warnings,
        "safe_to_print": safe,
        "requires_override": not safe,
    }


def main():
    base = load_base()
    if not V03_HTML.is_file():
        raise SystemExit(f"v0.3 UI not found: {V03_HTML}")
    base.COMBINED_HTML = V03_HTML
    base.build_preflight = lambda ifs, inspection: slot_aware_preflight(base, ifs, inspection)
    base.main()


if __name__ == "__main__":
    main()
