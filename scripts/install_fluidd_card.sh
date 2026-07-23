#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/opt/config/mod_data/ifs_spoolman"

CARD_SOURCE="$APP_DIR/ifs-spoolman-card.js"
LAYOUT_SOURCE="$APP_DIR/ifs-spoolman-layout.js"
DASHBOARD_SOURCE="$APP_DIR/ifs-spoolman-dashboard.js"
SELECTION_SOURCE="$APP_DIR/ifs-spoolman-selection.js"
CONTROLS_SOURCE="$APP_DIR/ifs-spoolman-controls.js"

FLUIDD_DIR="/root/fluidd"
INDEX="$FLUIDD_DIR/index.html"

CARD_TARGET_NAME="ifs-spoolman-card-v10.js"
LAYOUT_TARGET_NAME="ifs-spoolman-layout-v2.js"
DASHBOARD_TARGET_NAME="ifs-spoolman-dashboard-v1.js"
SELECTION_TARGET_NAME="ifs-spoolman-selection-v1.js"
CONTROLS_TARGET_NAME="ifs-spoolman-controls-v4.js"

CARD_TARGET="$FLUIDD_DIR/$CARD_TARGET_NAME"
LAYOUT_TARGET="$FLUIDD_DIR/$LAYOUT_TARGET_NAME"
DASHBOARD_TARGET="$FLUIDD_DIR/$DASHBOARD_TARGET_NAME"
SELECTION_TARGET="$FLUIDD_DIR/$SELECTION_TARGET_NAME"
CONTROLS_TARGET="$FLUIDD_DIR/$CONTROLS_TARGET_NAME"

PYTHON="/root/moonraker-env/bin/python3"

for FILE in \
    "$CARD_SOURCE" \
    "$LAYOUT_SOURCE" \
    "$DASHBOARD_SOURCE" \
    "$SELECTION_SOURCE" \
    "$CONTROLS_SOURCE"
do
    [ -f "$FILE" ] || {
        echo "$APP_NAME: не найден $FILE"
        exit 1
    }
done

[ -f "$INDEX" ] || {
    echo "$APP_NAME: не найден Fluidd index.html"
    exit 1
}

[ -x "$PYTHON" ] || {
    echo "$APP_NAME: не найден Python: $PYTHON"
    exit 1
}

cp "$CARD_SOURCE" "$CARD_TARGET"
cp "$LAYOUT_SOURCE" "$LAYOUT_TARGET"
cp "$DASHBOARD_SOURCE" "$DASHBOARD_TARGET"
cp "$SELECTION_SOURCE" "$SELECTION_TARGET"
cp "$CONTROLS_SOURCE" "$CONTROLS_TARGET"

"$PYTHON" - \
    "$INDEX" \
    "$CARD_TARGET_NAME" \
    "$LAYOUT_TARGET_NAME" \
    "$DASHBOARD_TARGET_NAME" \
    "$SELECTION_TARGET_NAME" \
    "$CONTROLS_TARGET_NAME" <<'PY'
import re
import sys
from pathlib import Path

index_path = Path(sys.argv[1])
card_name = sys.argv[2]
layout_name = sys.argv[3]
dashboard_name = sys.argv[4]
selection_name = sys.argv[5]
controls_name = sys.argv[6]

text = index_path.read_text(encoding="utf-8")

text = re.sub(
    r'\s*<script[^>]+src=["\'][^"\']*'
    r'ifs-spoolman-(?:card|layout|visibility|dashboard|selection|controls)[^"\']*'
    r'["\'][^>]*></script>',
    "",
    text,
)

scripts = (
    f'    <script defer src="./{card_name}"></script>\n'
    f'    <script defer src="./{layout_name}"></script>\n'
    f'    <script defer src="./{dashboard_name}"></script>\n'
    f'    <script defer src="./{selection_name}"></script>\n'
    f'    <script defer src="./{controls_name}"></script>\n'
)

if "</body>" not in text:
    raise SystemExit(
        "ОШИБКА: Fluidd index.html не содержит </body>"
    )

text = text.replace(
    "</body>",
    scripts + "</body>",
    1,
)

index_path.write_text(text, encoding="utf-8")
PY

for PATTERN in card layout visibility dashboard selection controls; do
    for FILE in "$FLUIDD_DIR"/ifs-spoolman-$PATTERN*.js; do
        [ -e "$FILE" ] || continue
        case "$FILE" in
            "$CARD_TARGET"|"$LAYOUT_TARGET"|"$DASHBOARD_TARGET"|"$SELECTION_TARGET"|"$CONTROLS_TARGET") continue ;;
        esac
        rm -f "$FILE"
    done
done

echo "$APP_NAME: Fluidd card установлен без изменения исходного интерфейса:"
echo "  $CARD_TARGET"
echo "$APP_NAME: Fluidd layout установлен:"
echo "  $LAYOUT_TARGET"
echo "$APP_NAME: Dashboard-only и сворачивание установлены:"
echo "  $DASHBOARD_TARGET"
echo "$APP_NAME: индикация активного и просматриваемого слота установлена:"
echo "  $SELECTION_TARGET"
echo "$APP_NAME: управление IFS и живая телеметрия установлены:"
echo "  $CONTROLS_TARGET"
