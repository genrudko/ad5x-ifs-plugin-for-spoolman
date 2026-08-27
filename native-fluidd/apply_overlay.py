#!/usr/bin/env python3
"""Apply the minimal standalone AD5X IFS native UI overlay to ghzserg/fluidd.

The script is intentionally fail-closed: every source edit requires one exact
anchor. A new upstream release that changes one of those anchors must not
silently produce an unknown build.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"


class OverlayError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")

    if new in text:
        return

    count = text.count(old)
    if count != 1:
        raise OverlayError(
            f"{label}: expected exactly one anchor in {path}, found {count}"
        )

    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def inject_locale(path: Path, block: str) -> None:
    text = path.read_text(encoding="utf-8")

    if "\n  ad5x_ifs:\n" in text:
        return

    if not text.startswith("app:\n"):
        raise OverlayError(f"locale root changed: {path}")

    path.write_text("app:\n" + block + text[len("app:\n"):], encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} /path/to/ghzserg-fluidd", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()

    required = [
        root / "package.json",
        root / "src/views/Dashboard.vue",
        root / "src/store/layout/state.ts",
        root / "src/locales/en.yaml",
        root / "src/locales/ru.yaml",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise OverlayError("not a Fluidd source checkout; missing: " + ", ".join(missing))

    component_source = (
        OVERLAY
        / "src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue"
    )
    if not component_source.is_file():
        raise OverlayError(f"overlay component missing: {component_source}")

    component_target = (
        root
        / "src/components/widgets/ad5x-ifs/Ad5xIfsCard.vue"
    )
    component_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(component_source, component_target)

    dashboard = root / "src/views/Dashboard.vue"
    replace_once(
        dashboard,
        "import AfcCard from '@/components/widgets/afc/AfcCard.vue'\n",
        "import AfcCard from '@/components/widgets/afc/AfcCard.vue'\n"
        "import Ad5xIfsCard from '@/components/widgets/ad5x-ifs/Ad5xIfsCard.vue'\n",
        "Dashboard import",
    )
    replace_once(
        dashboard,
        "    BeaconCard,\n    AfcCard\n",
        "    BeaconCard,\n    AfcCard,\n    Ad5xIfsCard\n",
        "Dashboard component registry",
    )

    layout = root / "src/store/layout/state.ts"
    replace_once(
        layout,
        "          { id: 'spoolman-card', enabled: true, collapsed: false },\n",
        "          { id: 'spoolman-card', enabled: true, collapsed: false },\n"
        "          { id: 'ad5x-ifs-card', enabled: true, collapsed: false },\n",
        "Dashboard layout",
    )

    inject_locale(
        root / "src/locales/en.yaml",
        "  ad5x_ifs:\n"
        "    title: \"AD5X IFS\"\n"
        "    connected: \"Connected\"\n"
        "    disconnected: \"Offline\"\n"
        "    manage: \"Manage\"\n"
        "    active: \"Active\"\n"
        "    active_slot: \"Active slot\"\n"
        "    assigned: \"Assigned\"\n"
        "    remaining: \"Remaining\"\n"
        "    moonraker_spool: \"Moonraker spool\"\n"
        "    unassigned: \"No Spoolman spool is assigned to this IFS slot.\"\n"
        "    unassigned_hint: \"Open Manage to assign a spool.\"\n"
        "    api_unavailable: \"IFS plugin API is unavailable\"\n"
        "    unnamed: \"Unnamed spool\"\n",
    )

    inject_locale(
        root / "src/locales/ru.yaml",
        "  ad5x_ifs:\n"
        "    title: \"AD5X IFS\"\n"
        "    connected: \"Подключено\"\n"
        "    disconnected: \"Нет связи\"\n"
        "    manage: \"Управление\"\n"
        "    active: \"Активный\"\n"
        "    active_slot: \"Активный слот\"\n"
        "    assigned: \"Назначено\"\n"
        "    remaining: \"Остаток\"\n"
        "    moonraker_spool: \"Катушка Moonraker\"\n"
        "    unassigned: \"К этому слоту IFS не назначена катушка Spoolman.\"\n"
        "    unassigned_hint: \"Откройте «Управление», чтобы назначить катушку.\"\n"
        "    api_unavailable: \"API плагина IFS недоступен\"\n"
        "    unnamed: \"Без названия\"\n",
    )

    print("AD5X IFS native Fluidd overlay applied")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OverlayError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
