#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
APP_DIR="/opt/config/mod_data/ifs_spoolman"

CARD_SOURCE="$APP_DIR/ifs-spoolman-card.js"
LAYOUT_SOURCE="$APP_DIR/ifs-spoolman-layout.js"
VISIBILITY_SOURCE="$APP_DIR/ifs-spoolman-visibility.js"
SELECTION_SOURCE="$APP_DIR/ifs-spoolman-selection.js"

FLUIDD_DIR="/root/fluidd"
INDEX="$FLUIDD_DIR/index.html"

CARD_TARGET_NAME="ifs-spoolman-card-v10.js"
LAYOUT_TARGET_NAME="ifs-spoolman-layout-v2.js"
VISIBILITY_TARGET_NAME="ifs-spoolman-visibility-v1.js"
SELECTION_TARGET_NAME="ifs-spoolman-selection-v1.js"

CARD_TARGET="$FLUIDD_DIR/$CARD_TARGET_NAME"
LAYOUT_TARGET="$FLUIDD_DIR/$LAYOUT_TARGET_NAME"
VISIBILITY_TARGET="$FLUIDD_DIR/$VISIBILITY_TARGET_NAME"
SELECTION_TARGET="$FLUIDD_DIR/$SELECTION_TARGET_NAME"

PYTHON="/root/moonraker-env/bin/python3"

for FILE in \
    "$CARD_SOURCE" \
    "$LAYOUT_SOURCE" \
    "$VISIBILITY_SOURCE" \
    "$SELECTION_SOURCE"
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
cp "$VISIBILITY_SOURCE" "$VISIBILITY_TARGET"
cp "$SELECTION_SOURCE" "$SELECTION_TARGET"

"$PYTHON" - \
    "$INDEX" \
    "$CARD_TARGET_NAME" \
    "$LAYOUT_TARGET_NAME" \
    "$VISIBILITY_TARGET_NAME" \
    "$SELECTION_TARGET_NAME" <<'PY'
import re
import sys
from pathlib import Path

index_path = Path(sys.argv[1])
card_name = sys.argv[2]
layout_name = sys.argv[3]
visibility_name = sys.argv[4]
selection_name = sys.argv[5]

text = index_path.read_text(encoding="utf-8")

text = re.sub(
    r'\s*<script[^>]+src=["\'][^"\']*'
    r'ifs-spoolman-(?:card|layout|visibility|selection)[^"\']*'
    r'["\'][^>]*></script>',
    "",
    text,
)

scripts = (
    f'    <script defer src="./{card_name}"></script>\n'
    f'    <script defer src="./{layout_name}"></script>\n'
    f'    <script defer src="./{visibility_name}"></script>\n'
    f'    <script defer src="./{selection_name}"></script>\n'
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

for PATTERN in card layout visibility selection; do
    for FILE in "$FLUIDD_DIR"/ifs-spoolman-$PATTERN*.js; do
        [ -e "$FILE" ] || continue
        case "$FILE" in
            "$CARD_TARGET"|"$LAYOUT_TARGET"|"$VISIBILITY_TARGET"|"$SELECTION_TARGET") continue ;;
        esac
        rm -f "$FILE"
    done
done

echo "$APP_NAME: Fluidd card установлен:"
echo "  $CARD_TARGET"
echo "$APP_NAME: Fluidd layout установлен:"
echo "  $LAYOUT_TARGET"
echo "$APP_NAME: ограничение показа Dashboard установлено:"
echo "  $VISIBILITY_TARGET"
echo "$APP_NAME: индикация активного и просматриваемого слота установлена:"
echo "  $SELECTION_TARGET"
