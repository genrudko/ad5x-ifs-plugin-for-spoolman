#!/bin/sh
set -eu

APP_NAME="AD5X IFS Manager"
APP_DIR="/opt/config/mod_data/ifs_spoolman"
CARD_SOURCE="$APP_DIR/ifs-spoolman-card.js"

FLUIDD_DIR="/root/fluidd"
INDEX="$FLUIDD_DIR/index.html"
CARD_TARGET_NAME="ifs-spoolman-card-v11.js"
CARD_TARGET="$FLUIDD_DIR/$CARD_TARGET_NAME"
PYTHON="/root/moonraker-env/bin/python3"

[ -f "$CARD_SOURCE" ] || {
    echo "$APP_NAME: не найден $CARD_SOURCE"
    exit 1
}

[ -f "$INDEX" ] || {
    echo "$APP_NAME: не найден Fluidd index.html"
    exit 1
}

[ -x "$PYTHON" ] || {
    echo "$APP_NAME: не найден Python: $PYTHON"
    exit 1
}

cp "$CARD_SOURCE" "$CARD_TARGET"

"$PYTHON" - "$INDEX" "$CARD_TARGET_NAME" <<'PY'
import re
import sys
from pathlib import Path

index_path = Path(sys.argv[1])
card_name = sys.argv[2]
text = index_path.read_text(encoding="utf-8")

text = re.sub(
    r'\s*<script[^>]+src=["\'][^"\']*'
    r'ifs-spoolman-(?:card|layout|visibility|selection)[^"\']*'
    r'["\'][^>]*></script>',
    "",
    text,
)

script = f'    <script defer src="./{card_name}"></script>\n'

if "</body>" not in text:
    raise SystemExit(
        "ОШИБКА: Fluidd index.html не содержит </body>"
    )

text = text.replace(
    "</body>",
    script + "</body>",
    1,
)

index_path.write_text(text, encoding="utf-8")
PY

for PATTERN in card layout visibility selection; do
    for FILE in "$FLUIDD_DIR"/ifs-spoolman-$PATTERN*.js; do
        [ -e "$FILE" ] || continue
        [ "$FILE" = "$CARD_TARGET" ] && continue
        rm -f "$FILE"
    done
done

echo "$APP_NAME: dashboard-карточка установлена:"
echo "  $CARD_TARGET"
echo "$APP_NAME: старые глобальные layout/visibility/selection-скрипты удалены"
