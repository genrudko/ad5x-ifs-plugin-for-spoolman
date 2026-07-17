#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
FLUIDD_DIR="/root/fluidd"
INDEX="$FLUIDD_DIR/index.html"
PYTHON="/root/moonraker-env/bin/python3"

if [ -f "$INDEX" ] && [ -x "$PYTHON" ]; then
    "$PYTHON" - "$INDEX" <<'PY'
import re
import sys
from pathlib import Path

index_path = Path(sys.argv[1])
text = index_path.read_text(encoding="utf-8")

text = re.sub(
    r'\s*<script[^>]+src=["\'][^"\']*'
    r'ifs-spoolman-(?:card|layout|visibility)[^"\']*'
    r'["\'][^>]*></script>',
    "",
    text,
)

index_path.write_text(text, encoding="utf-8")
PY
fi

rm -f \
    "$FLUIDD_DIR"/ifs-spoolman-card*.js \
    "$FLUIDD_DIR"/ifs-spoolman-layout*.js \
    "$FLUIDD_DIR"/ifs-spoolman-visibility*.js

echo "$APP_NAME: интеграция Fluidd удалена."
