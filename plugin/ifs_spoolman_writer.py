#!/usr/bin/env python3
"""Phase B2: safe writes of native Z-Mod slot colour and material metadata."""

import json
import os
import shutil
import stat
import threading
import time
import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_runtime as runtime


RUNTIME_VERSION = "0.7.3-beta"
BACKUP_DIR = os.path.join(core.APP_DIR, "backups", "zmod_metadata")
_write_lock = threading.RLock()
_original_metadata = runtime.zmod_filament_metadata
_original_public_config = runtime.public_config
_original_build_health = runtime.build_health
_BaseHandler = runtime.RuntimeHandler


def _validate_slot(value):
    if isinstance(value, bool):
        raise ValueError("slot должен быть целым числом от 1 до 4")
    try:
        slot = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("slot должен быть целым числом от 1 до 4") from exc
    if not 1 <= slot <= int(core.SLOT_COUNT):
        raise ValueError(f"slot должен быть в диапазоне 1–{core.SLOT_COUNT}")
    return slot


def _validate_color(value):
    if not isinstance(value, str):
        raise ValueError("color должен быть строкой вида #RRGGBB")
    color = value.strip().upper()
    if len(color) != 7 or not color.startswith("#"):
        raise ValueError("color должен иметь формат #RRGGBB")
    if any(character not in "0123456789ABCDEF" for character in color[1:]):
        raise ValueError("color должен иметь формат #RRGGBB")
    return color


def _validate_material(value):
    if not isinstance(value, str):
        raise ValueError("material должен быть строкой")
    material = value.strip()
    if not material:
        raise ValueError("material не должен быть пустым")
    if len(material) > 32:
        raise ValueError("material не должен быть длиннее 32 символов")
    if any(ord(character) < 32 or character in "{}[]\"'\\" for character in material):
        raise ValueError("material содержит недопустимые символы")
    if not all(character.isalnum() or character in " +._-/" for character in material):
        raise ValueError("material содержит недопустимые символы")
    return material


def _allowed_realpaths():
    result = set()
    for path in runtime.KNOWN_METADATA_FILES:
        if os.path.exists(path):
            result.add(os.path.realpath(path))
    return result


def _load_target():
    metadata = _original_metadata(force=True)
    source = metadata.get("source")
    if not metadata.get("available") or not isinstance(source, dict):
        raise RuntimeError("Штатный источник FFMInfo не найден")

    path = source.get("path")
    if not isinstance(path, str) or not path:
        raise RuntimeError("Источник FFMInfo не содержит путь")

    realpath = os.path.realpath(path)
    if realpath not in _allowed_realpaths():
        raise RuntimeError("Источник FFMInfo не входит в разрешённый список")
    if not os.path.isfile(realpath):
        raise RuntimeError("Файл Adventurer5M.json не найден")

    return path, realpath


def _read_json(path):
    with open(path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise RuntimeError("Adventurer5M.json должен содержать JSON-объект")
    ffm_info = payload.get("FFMInfo")
    if not isinstance(ffm_info, dict):
        raise RuntimeError("В Adventurer5M.json отсутствует раздел FFMInfo")
    return payload, ffm_info


def _backup_file(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    nanoseconds = time.time_ns() % 1_000_000_000
    backup = os.path.join(
        BACKUP_DIR,
        f"Adventurer5M_{stamp}_{nanoseconds:09d}.json",
    )
    shutil.copy2(path, backup)
    return backup


def _atomic_replace_json(path, payload, original_stat):
    directory = os.path.dirname(path)
    temporary = os.path.join(
        directory,
        f".{os.path.basename(path)}.ifs-manager-{os.getpid()}-{time.time_ns()}.tmp",
    )

    try:
        with open(temporary, "x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=4)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        try:
            os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        except PermissionError:
            pass

        os.replace(temporary, path)

        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _invalidate_metadata_cache():
    with runtime._metadata_lock:
        runtime._metadata_cache["created_monotonic"] = 0.0
        runtime._metadata_cache["payload"] = None


def update_slot_metadata(body):
    if not isinstance(body, dict):
        raise ValueError("Тело запроса должно быть JSON-объектом")

    allowed = {"slot", "color", "material"}
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ValueError("Неизвестные параметры: " + ", ".join(unknown))

    slot = _validate_slot(body.get("slot"))
    has_color = "color" in body
    has_material = "material" in body
    if not has_color and not has_material:
        raise ValueError("Нужно передать color и/или material")

    color = _validate_color(body["color"]) if has_color else None
    material = _validate_material(body["material"]) if has_material else None

    with _write_lock:
        source_path, target = _load_target()
        before_stat = os.stat(target)
        payload, ffm_info = _read_json(target)

        color_key = f"ffmColor{slot}"
        material_key = f"ffmType{slot}"
        previous = {
            "color": runtime._normalize_color(ffm_info.get(color_key)),
            "material": runtime._normalize_material(ffm_info.get(material_key)),
        }

        if has_color:
            ffm_info[color_key] = color
        if has_material:
            ffm_info[material_key] = material

        changed = (
            (has_color and previous["color"] != color)
            or (has_material and previous["material"] != material)
        )

        if not changed:
            _invalidate_metadata_cache()
            metadata = _original_metadata(force=True)
            return {
                "ok": True,
                "changed": False,
                "slot": slot,
                "previous": previous,
                "current": metadata["slots"][str(slot)],
                "source": metadata.get("source"),
                "backup": None,
            }

        current_stat = os.stat(target)
        if (
            current_stat.st_dev != before_stat.st_dev
            or current_stat.st_ino != before_stat.st_ino
            or current_stat.st_mtime_ns != before_stat.st_mtime_ns
            or current_stat.st_size != before_stat.st_size
        ):
            raise RuntimeError("Adventurer5M.json изменился во время подготовки записи")

        backup = _backup_file(target)
        try:
            _atomic_replace_json(target, payload, before_stat)
            verified_payload, verified_ffm = _read_json(target)
            del verified_payload

            verified_color = runtime._normalize_color(verified_ffm.get(color_key))
            verified_material = runtime._normalize_material(verified_ffm.get(material_key))
            if has_color and verified_color != color:
                raise RuntimeError("Проверка записанного цвета не пройдена")
            if has_material and verified_material != material:
                raise RuntimeError("Проверка записанного материала не пройдена")
        except Exception:
            shutil.copy2(backup, target)
            raise

        _invalidate_metadata_cache()
        metadata = _original_metadata(force=True)
        current = metadata["slots"][str(slot)]

        core.event_log(
            "info",
            "zmod_slot_metadata_updated",
            "Изменены штатные метаданные слота Z-Mod",
            slot=slot,
            previous=previous,
            current={
                "color": current.get("color"),
                "material": current.get("material"),
            },
            source=source_path,
            target=target,
            backup=backup,
        )

        return {
            "ok": True,
            "changed": True,
            "slot": slot,
            "previous": previous,
            "current": current,
            "source": metadata.get("source"),
            "backup": backup,
        }


def zmod_filament_metadata(force=False):
    payload = _original_metadata(force=force)
    payload["read_only"] = False
    payload["write_actions_enabled"] = bool(payload.get("available"))
    payload["write_endpoint"] = "/api/zmod/filaments/slot"
    return payload


def public_config():
    payload = _original_public_config()
    payload["application_version"] = RUNTIME_VERSION
    payload["zmod_metadata"] = {
        "endpoint": "/api/zmod/filaments",
        "write_endpoint": "/api/zmod/filaments/slot",
        "read_only": False,
        "write_actions_enabled": True,
        "schema": "ffminfo-v1",
    }
    return payload


def build_health():
    health = _original_build_health()
    metadata = zmod_filament_metadata()
    health["version"] = RUNTIME_VERSION
    component = health.setdefault("components", {}).setdefault("zmod_metadata", {})
    component["ok"] = metadata.get("available") is True
    component["read_only"] = False
    component["write_actions_enabled"] = metadata.get("write_actions_enabled") is True
    component["write_endpoint"] = "/api/zmod/filaments/slot"
    return health


class WriteRuntimeHandler(_BaseHandler):
    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/zmod/filaments/slot":
            try:
                result = update_slot_metadata(self.read_json())
                self.send_json(200, result)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                core.event_log(
                    "error",
                    "zmod_slot_metadata_update_failed",
                    "Не удалось изменить штатные метаданные слота Z-Mod",
                    error=str(exc),
                )
                self.send_json(500, {"error": str(exc)})
            return
        super().do_POST()


runtime.RUNTIME_VERSION = RUNTIME_VERSION
runtime.zmod_filament_metadata = zmod_filament_metadata
core.APP_VERSION = RUNTIME_VERSION
core.public_config = public_config
core.build_health = build_health
core.Handler = WriteRuntimeHandler


if __name__ == "__main__":
    core.main()
