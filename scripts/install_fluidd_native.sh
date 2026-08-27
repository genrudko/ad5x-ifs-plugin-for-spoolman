#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
ROLLING_TAG="fluidd-compatibility"
PATCH_REVISION="${AD5X_IFS_FLUIDD_PATCH_REVISION:-1}"
REPO="genrudko/ad5x-ifs-plugin-for-spoolman"

find_moonraker_pid() {
    for P in /proc/[0-9]*; do
        [ -r "$P/cmdline" ] || continue
        CMD="$(tr '\0' ' ' <"$P/cmdline" 2>/dev/null || true)"
        case "$CMD" in
            *moonraker.py*)
                [ -d "$P/root" ] || continue
                echo "${P##*/}"
                return 0
                ;;
        esac
    done
    return 1
}

[ "$(id -u)" = "0" ] || {
    echo "$APP_NAME: run this script over SSH as root." >&2
    exit 1
}

MOON_PID="$(find_moonraker_pid 2>/dev/null || true)"
[ -n "$MOON_PID" ] || {
    echo "$APP_NAME: Moonraker process/chroot not found." >&2
    exit 1
}

ROOT="/proc/$MOON_PID/root"

chroot "$ROOT" /bin/sh -s -- "$REPO" "$ROLLING_TAG" "$PATCH_REVISION" <<'INNER'
set -eu

REPO="$1"
ROLLING_TAG="$2"
PATCH_REVISION="$3"
FLUIDD_DIR="/root/fluidd"
PREVIOUS_DIR="/root/fluidd.ifs-previous"
WORK_DIR="/root/.ad5x-ifs-native-fluidd.$$"
NEW_DIR="$WORK_DIR/new"
ZIP_FILE="$WORK_DIR/fluidd.zip"
SHA_FILE="$WORK_DIR/fluidd.zip.sha256"
OLD_NATIVE_DIR="$WORK_DIR/old-native"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT HUP INT TERM

fail() {
    echo "AD5X IFS native Fluidd: $*" >&2
    exit 1
}

for CMD in wget sha256sum unzip grep mv rm mkdir cat; do
    command -v "$CMD" >/dev/null 2>&1 || fail "required command not found: $CMD"
done

[ -d "$FLUIDD_DIR" ] || fail "Fluidd directory not found: $FLUIDD_DIR"
[ -f "$FLUIDD_DIR/.version" ] || fail "Fluidd .version is missing"

UPSTREAM_TAG="$(cat "$FLUIDD_DIR/.version" 2>/dev/null || true)"
case "$UPSTREAM_TAG" in
    v[0-9]*.[0-9]*.[0-9]*) ;;
    *) fail "unsupported Fluidd version value: $UPSTREAM_TAG" ;;
esac

ASSET_NAME="fluidd-${UPSTREAM_TAG}-ifs-ui-v${PATCH_REVISION}.zip"
BASE_URL="https://github.com/${REPO}/releases/download/${ROLLING_TAG}"

CURRENT_NATIVE=0
if [ -f "$FLUIDD_DIR/ad5x_ifs_native.json" ]; then
    CURRENT_NATIVE=1
    if grep -Eq '"patch_revision"[[:space:]]*:[[:space:]]*'"$PATCH_REVISION"'([[:space:],}]|$)' \
        "$FLUIDD_DIR/ad5x_ifs_native.json" \
        && grep -F '"upstream_tag": "'"$UPSTREAM_TAG"'"' \
        "$FLUIDD_DIR/ad5x_ifs_native.json" >/dev/null 2>&1
    then
        echo "AD5X IFS native Fluidd already installed: $UPSTREAM_TAG / patch $PATCH_REVISION"
        exit 0
    fi
fi

mkdir -p "$WORK_DIR" "$NEW_DIR"

echo "Fluidd upstream: $UPSTREAM_TAG"
echo "Native IFS UI patch: $PATCH_REVISION"
echo "Downloading: $ASSET_NAME"

wget -qO "$ZIP_FILE" "$BASE_URL/$ASSET_NAME" || fail "compatible native Fluidd build is not published yet"
wget -qO "$SHA_FILE" "$BASE_URL/$ASSET_NAME.sha256" || fail "checksum file is unavailable"

EXPECTED_SHA="$(awk '{print $1; exit}' "$SHA_FILE")"
[ -n "$EXPECTED_SHA" ] || fail "empty checksum file"
ACTUAL_SHA="$(sha256sum "$ZIP_FILE" | awk '{print $1}')"
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || fail "SHA256 mismatch"

unzip -q "$ZIP_FILE" -d "$NEW_DIR" || fail "cannot unpack compatibility ZIP"

[ -f "$NEW_DIR/index.html" ] || fail "new Fluidd index.html is missing"
[ -f "$NEW_DIR/.version" ] || fail "new Fluidd .version is missing"
[ "$(cat "$NEW_DIR/.version")" = "$UPSTREAM_TAG" ] || fail "new build version does not match installed Fluidd"
[ -f "$NEW_DIR/release_info.json" ] || fail "new release_info.json is missing"
grep -F '"project_name":"fluidd"' "$NEW_DIR/release_info.json" >/dev/null || fail "wrong Fluidd project identity"
grep -F '"project_owner":"ghzserg"' "$NEW_DIR/release_info.json" >/dev/null || fail "wrong Fluidd owner identity"
grep -F '"version":"'"$UPSTREAM_TAG"'"' "$NEW_DIR/release_info.json" >/dev/null || fail "wrong Fluidd release identity"
[ -f "$NEW_DIR/ad5x_ifs_native.json" ] || fail "native compatibility marker is missing"
grep -F '"upstream_repository": "ghzserg/fluidd"' "$NEW_DIR/ad5x_ifs_native.json" >/dev/null || fail "wrong upstream repository marker"
grep -F '"upstream_tag": "'"$UPSTREAM_TAG"'"' "$NEW_DIR/ad5x_ifs_native.json" >/dev/null || fail "wrong upstream tag marker"
grep -Eq '"patch_revision"[[:space:]]*:[[:space:]]*'"$PATCH_REVISION"'([[:space:],}]|$)' "$NEW_DIR/ad5x_ifs_native.json" || fail "wrong patch revision marker"

rollback_swap() {
    if [ -d "$FLUIDD_DIR" ]; then
        rm -rf "$FLUIDD_DIR.failed" 2>/dev/null || true
        mv "$FLUIDD_DIR" "$FLUIDD_DIR.failed" 2>/dev/null || true
    fi

    if [ "$CURRENT_NATIVE" -eq 1 ] && [ -d "$OLD_NATIVE_DIR" ]; then
        mv "$OLD_NATIVE_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    elif [ -d "$PREVIOUS_DIR" ]; then
        mv "$PREVIOUS_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    fi

    rm -rf "$FLUIDD_DIR.failed" 2>/dev/null || true
}

if [ "$CURRENT_NATIVE" -eq 1 ]; then
    mv "$FLUIDD_DIR" "$OLD_NATIVE_DIR" || fail "cannot stage current native Fluidd"
else
    rm -rf "$PREVIOUS_DIR"
    mv "$FLUIDD_DIR" "$PREVIOUS_DIR" || fail "cannot preserve current Fluidd for rollback"
fi

if ! mv "$NEW_DIR" "$FLUIDD_DIR"; then
    rollback_swap
    fail "cannot activate native Fluidd build; previous Fluidd restored"
fi

if [ ! -f "$FLUIDD_DIR/index.html" ] || [ ! -f "$FLUIDD_DIR/ad5x_ifs_native.json" ]; then
    rollback_swap
    fail "post-install validation failed; previous Fluidd restored"
fi

if [ "$CURRENT_NATIVE" -eq 1 ]; then
    rm -rf "$OLD_NATIVE_DIR"
fi

rm -f "$FLUIDD_DIR"/ifs-spoolman-card*.js \
      "$FLUIDD_DIR"/ifs-spoolman-layout*.js \
      "$FLUIDD_DIR"/ifs-spoolman-dashboard*.js \
      "$FLUIDD_DIR"/ifs-spoolman-selection*.js \
      "$FLUIDD_DIR"/ifs-spoolman-visibility*.js \
      "$FLUIDD_DIR"/ifs-spoolman-controls*.js 2>/dev/null || true

echo "AD5X IFS native Fluidd installed successfully."
echo "Fluidd identity: ghzserg/fluidd $UPSTREAM_TAG"
echo "Native patch revision: $PATCH_REVISION"
echo "Rollback snapshot: $PREVIOUS_DIR"
INNER
