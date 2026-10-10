#!/bin/sh
set -eu

APP_NAME="AD5X IFS Plugin for Spoolman"
UPSTREAM_REPO="${AD5X_IFS_FLUIDD_UPSTREAM_REPO:-ghzserg/fluidd}"
ASSET_NAME="${AD5X_IFS_FLUIDD_ASSET_NAME:-fluidd.zip}"

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

fail() {
    echo "$APP_NAME: $*" >&2
    exit 1
}

valid_fluidd_version() {
    case "$1" in
        v[0-9]*.[0-9]*.[0-9]*) return 0 ;;
    esac
    return 1
}

legacy_present() {
    LEGACY_DIR="$1"
    [ -d "$LEGACY_DIR" ] || return 1

    if [ -f "$LEGACY_DIR/index.html" ] &&
        grep -Eq 'ifs-spoolman-(card|layout|visibility|dashboard|selection|controls)' \
            "$LEGACY_DIR/index.html"
    then
        return 0
    fi

    for LEGACY_FILE in \
        "$LEGACY_DIR"/ifs-spoolman-card*.js \
        "$LEGACY_DIR"/ifs-spoolman-layout*.js \
        "$LEGACY_DIR"/ifs-spoolman-dashboard*.js \
        "$LEGACY_DIR"/ifs-spoolman-selection*.js \
        "$LEGACY_DIR"/ifs-spoolman-visibility*.js \
        "$LEGACY_DIR"/ifs-spoolman-controls*.js
    do
        [ -e "$LEGACY_FILE" ] && return 0
    done

    return 1
}

clean_fluidd_dir() {
    CLEAN_DIR="$1"
    EXPECTED_VERSION="$2"

    [ -d "$CLEAN_DIR" ] || return 1
    [ -f "$CLEAN_DIR/index.html" ] || return 1
    [ -f "$CLEAN_DIR/.version" ] || return 1
    [ "$(cat "$CLEAN_DIR/.version" 2>/dev/null || true)" = "$EXPECTED_VERSION" ] || return 1
    [ ! -f "$CLEAN_DIR/ad5x_ifs_native.json" ] || return 1
    legacy_present "$CLEAN_DIR" && return 1
    return 0
}

resolve_fluidd_version() {
    DIR="$1"
    VERSION="$(cat "$DIR/.version" 2>/dev/null || true)"
    if valid_fluidd_version "$VERSION"; then
        printf '%s\n' "$VERSION"
        return 0
    fi

    INFO="$DIR/release_info.json"
    if [ -f "$INFO" ]; then
        VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$INFO" | head -n 1)"
        if valid_fluidd_version "$VERSION"; then
            printf '%s\n' "$VERSION"
            return 0
        fi
    fi
    return 1
}

[ "$(id -u)" = "0" ] || fail "run this script over SSH as root"

MOON_PID="$(find_moonraker_pid 2>/dev/null || true)"
[ -n "$MOON_PID" ] || fail "Moonraker process/chroot not found"

ROOT="/proc/$MOON_PID/root"
FLUIDD_DIR="$ROOT/root/fluidd"
PREVIOUS_DIR="$ROOT/root/fluidd.ifs-previous"
WORK_INNER="/root/.ad5x-ifs-fluidd-restore.$$"
WORK_DIR="$ROOT$WORK_INNER"
STAGE_INNER="$WORK_INNER/stage"
STAGE_DIR="$ROOT$STAGE_INNER"
FAILED_DIR="$ROOT/root/.fluidd.ifs-native-removed.$$"

[ -d "$FLUIDD_DIR" ] || fail "current Fluidd directory is missing"

CURRENT_VERSION="$(resolve_fluidd_version "$FLUIDD_DIR" 2>/dev/null || true)"
valid_fluidd_version "$CURRENT_VERSION" ||
    fail "cannot determine the current Fluidd version"

cleanup() {
    rm -rf "$WORK_DIR" "$FAILED_DIR" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

SOURCE_DIR=""
SOURCE_KIND=""

if clean_fluidd_dir "$PREVIOUS_DIR" "$CURRENT_VERSION"; then
    echo "AD5X IFS native Fluidd: using same-version rollback snapshot $CURRENT_VERSION."
    SOURCE_DIR="$PREVIOUS_DIR"
    SOURCE_KIND="snapshot"
else
    PREVIOUS_VERSION="$(resolve_fluidd_version "$PREVIOUS_DIR" 2>/dev/null || true)"
    if [ -d "$PREVIOUS_DIR" ]; then
        echo "AD5X IFS native Fluidd: rollback snapshot is unusable or version-mismatched (${PREVIOUS_VERSION:-unknown} -> $CURRENT_VERSION); fetching clean same-version Fluidd."
    else
        echo "AD5X IFS native Fluidd: rollback snapshot is absent; fetching clean same-version Fluidd $CURRENT_VERSION."
    fi

    chroot "$ROOT" /bin/sh -c '[ -x /root/moonraker-env/bin/python3 ]' ||
        fail "Moonraker Python environment is unavailable for trusted HTTPS recovery"

    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"

    chroot "$ROOT" /root/moonraker-env/bin/python3 - \
        "$CURRENT_VERSION" "$UPSTREAM_REPO" "$ASSET_NAME" "$STAGE_INNER" <<'PY'
import hashlib
import json
import pathlib
import shutil
import sys
import urllib.request
import zipfile

version, repo, asset_name, stage_arg = sys.argv[1:5]
owner, project = repo.split("/", 1)
stage = pathlib.Path(stage_arg)
work = stage.parent
archive = work / asset_name

headers = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "ad5x-ifs-spoolman-uninstaller",
}
api_url = f"https://api.github.com/repos/{repo}/releases/tags/{version}"
with urllib.request.urlopen(
    urllib.request.Request(api_url, headers=headers),
    timeout=30,
) as response:
    release = json.load(response)

asset = next(
    (item for item in release.get("assets", []) if item.get("name") == asset_name),
    None,
)
if asset is None:
    raise SystemExit(f"release {version} has no {asset_name} asset")

download_url = asset.get("browser_download_url")
if not download_url:
    raise SystemExit("release asset has no download URL")

digest = asset.get("digest") or ""
expected_sha = ""
if digest:
    algorithm, separator, value = digest.partition(":")
    if separator != ":" or algorithm.lower() != "sha256" or len(value) != 64:
        raise SystemExit(f"unsupported release digest: {digest!r}")
    expected_sha = value.lower()

request = urllib.request.Request(download_url, headers={"User-Agent": headers["User-Agent"]})
sha256 = hashlib.sha256()
with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        sha256.update(chunk)
        output.write(chunk)

actual_sha = sha256.hexdigest()
if expected_sha and actual_sha != expected_sha:
    raise SystemExit(
        f"SHA256 mismatch for {asset_name}: expected {expected_sha}, got {actual_sha}"
    )

if stage.exists():
    shutil.rmtree(stage)
stage.mkdir(parents=True)

stage_root = stage.resolve()
with zipfile.ZipFile(archive) as zf:
    for info in zf.infolist():
        name = pathlib.PurePosixPath(info.filename)
        if name.is_absolute() or ".." in name.parts:
            raise SystemExit(f"unsafe path in Fluidd archive: {info.filename!r}")
        destination = (stage / pathlib.Path(*name.parts)).resolve()
        if destination != stage_root and stage_root not in destination.parents:
            raise SystemExit(f"unsafe extraction target: {info.filename!r}")
    zf.extractall(stage)

version_file = stage / ".version"
index_file = stage / "index.html"
release_info_file = stage / "release_info.json"
marker_file = stage / "ad5x_ifs_native.json"

if not index_file.is_file():
    raise SystemExit("downloaded Fluidd has no index.html")
if not version_file.is_file() or version_file.read_text().strip() != version:
    raise SystemExit("downloaded Fluidd version does not match the installed version")
if marker_file.exists():
    raise SystemExit("downloaded Fluidd unexpectedly contains the AD5X IFS marker")
if not release_info_file.is_file():
    raise SystemExit("downloaded Fluidd has no release_info.json")

release_info = json.loads(release_info_file.read_text())
if (
    release_info.get("project_owner") != owner
    or release_info.get("project_name") != project
    or release_info.get("version") != version
):
    raise SystemExit("downloaded Fluidd release identity is invalid")

print(f"Downloaded clean {repo} {version}; SHA256={actual_sha}")
PY

    clean_fluidd_dir "$STAGE_DIR" "$CURRENT_VERSION" ||
        fail "downloaded Fluidd failed post-download validation"

    SOURCE_DIR="$STAGE_DIR"
    SOURCE_KIND="download"
fi

rm -rf "$FAILED_DIR"
mv "$FLUIDD_DIR" "$FAILED_DIR"

if ! mv "$SOURCE_DIR" "$FLUIDD_DIR"; then
    mv "$FAILED_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    fail "cannot activate clean Fluidd; previous Fluidd restored"
fi

if ! clean_fluidd_dir "$FLUIDD_DIR" "$CURRENT_VERSION"; then
    mv "$FLUIDD_DIR" "$SOURCE_DIR" 2>/dev/null || true
    mv "$FAILED_DIR" "$FLUIDD_DIR" 2>/dev/null || true
    fail "clean Fluidd validation failed after activation; native Fluidd restored"
fi

rm -rf "$FAILED_DIR"

if [ "$SOURCE_KIND" = "download" ]; then
    # A stale/mismatched snapshot is plugin-owned state and is no longer useful
    # after a verified clean same-version distribution has been activated.
    rm -rf "$PREVIOUS_DIR"
fi

trap - EXIT HUP INT TERM
rm -rf "$WORK_DIR"

echo "AD5X IFS native Fluidd removed."
echo "Restored clean Fluidd: $CURRENT_VERSION ($SOURCE_KIND)"
