#!/usr/bin/env python3
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def first_existing(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]

APP_DIR = first_existing([
    "/root/printer_data/config/mod_data/ifs_spoolman",
    "/usr/data/config/mod_data/ifs_spoolman",
    "/opt/config/mod_data/ifs_spoolman",
])
ASSIGNMENTS_FILE = os.path.join(APP_DIR, "assignments.json")
FF_CONFIG = first_existing([
    "/usr/prog/config/Adventurer5M.json",
    "/root/printer_data/config/Adventurer5M.json",
])
# IFS_SPOOLMAN_CONFIG_V0_3
APP_VERSION = "0.5.0-beta"
CONFIG_SCHEMA_VERSION = 1
CONFIG_FILE = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "moonraker_url": "http://127.0.0.1:7125",
    "listen_host": "0.0.0.0",
    "listen_port": 7913,
    "slot_count": 4,
    "poll_interval": 1.0,
    "http_timeout": 5.0,
    "spoolman_proxy_timeout": 10.0,
    "switch_confirmation_reads": 3,
    "switch_confirmation_interval": 0.25,
    "switch_cooldown": 2.0,
    "sync_retry_count": 3,
    "sync_retry_delay": 1.0,
    "event_log_max_bytes": 524288,
    "event_log_backup_count": 3,
    "fluidd_integration": True,
}

CONFIG_KEYS = frozenset(DEFAULT_CONFIG)


def validate_config(raw):
    if not isinstance(raw, dict):
        raise ValueError(
            "config.json: корневое значение должно быть объектом"
        )

    unknown = sorted(set(raw) - CONFIG_KEYS)

    if unknown:
        raise ValueError(
            "config.json: неизвестные параметры: "
            + ", ".join(unknown)
        )

    result = dict(DEFAULT_CONFIG)
    result.update(raw)

    def plain_int(name, minimum, maximum):
        value = result[name]

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"config.json: {name} должен быть целым числом"
            )

        if not minimum <= value <= maximum:
            raise ValueError(
                f"config.json: {name} должен быть "
                f"в диапазоне {minimum}–{maximum}"
            )

        return value

    def number(name, minimum, maximum):
        value = result[name]

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise ValueError(
                f"config.json: {name} должен быть числом"
            )

        value = float(value)

        if not minimum <= value <= maximum:
            raise ValueError(
                f"config.json: {name} должен быть "
                f"в диапазоне {minimum}–{maximum}"
            )

        return value

    schema_version = plain_int("schema_version", 1, 1)

    moonraker_url = result["moonraker_url"]

    if not isinstance(moonraker_url, str):
        raise ValueError(
            "config.json: moonraker_url должен быть строкой"
        )

    moonraker_url = moonraker_url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(moonraker_url)

    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "config.json: moonraker_url должен быть корректным "
            "HTTP/HTTPS URL без учётных данных, query и fragment"
        )

    listen_host = result["listen_host"]

    if not isinstance(listen_host, str) or not listen_host.strip():
        raise ValueError(
            "config.json: listen_host должен быть непустой строкой"
        )

    fluidd_integration = result["fluidd_integration"]

    if not isinstance(fluidd_integration, bool):
        raise ValueError(
            "config.json: fluidd_integration должен быть "
            "true или false"
        )

    return {
        "schema_version": schema_version,
        "moonraker_url": moonraker_url,
        "listen_host": listen_host.strip(),
        "listen_port": plain_int("listen_port", 1, 65535),
        "slot_count": plain_int("slot_count", 1, 32),
        "poll_interval": number("poll_interval", 0.1, 60.0),
        "http_timeout": number("http_timeout", 0.5, 120.0),
        "spoolman_proxy_timeout": number(
            "spoolman_proxy_timeout",
            0.5,
            120.0,
        ),
        "switch_confirmation_reads": plain_int(
            "switch_confirmation_reads",
            1,
            20,
        ),
        "switch_confirmation_interval": number(
            "switch_confirmation_interval",
            0.05,
            10.0,
        ),
        "switch_cooldown": number(
            "switch_cooldown",
            0.0,
            60.0,
        ),
        "sync_retry_count": plain_int(
            "sync_retry_count",
            1,
            20,
        ),
        "sync_retry_delay": number(
            "sync_retry_delay",
            0.0,
            60.0,
        ),
        "event_log_max_bytes": plain_int(
            "event_log_max_bytes",
            65536,
            10485760,
        ),
        "event_log_backup_count": plain_int(
            "event_log_backup_count",
            1,
            20,
        ),
        "fluidd_integration": fluidd_integration,
    }


def load_config():
    if not os.path.exists(CONFIG_FILE):
        atomic_write_json(CONFIG_FILE, DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as stream:
            raw = json.load(stream)

        config = validate_config(raw)
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось загрузить конфигурацию "
            f"{CONFIG_FILE}: {exc}"
        ) from exc

    normalized = json.dumps(
        config,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as stream:
            current = stream.read()
    except OSError:
        current = ""

    if current != normalized:
        temporary = CONFIG_FILE + ".tmp"

        with open(temporary, "w", encoding="utf-8") as stream:
            stream.write(normalized)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary, CONFIG_FILE)

    return config


def public_config():
    return {
        "application": "AD5X IFS Plugin for Spoolman",
        "application_version": APP_VERSION,
        "schema_version": CONFIG["schema_version"],
        "moonraker_url": CONFIG["moonraker_url"],
        "listen_host": CONFIG["listen_host"],
        "listen_port": CONFIG["listen_port"],
        "slot_count": CONFIG["slot_count"],
        "poll_interval": CONFIG["poll_interval"],
        "http_timeout": CONFIG["http_timeout"],
        "spoolman_proxy_timeout": (
            CONFIG["spoolman_proxy_timeout"]
        ),
        "switch_confirmation_reads": (
            CONFIG["switch_confirmation_reads"]
        ),
        "switch_confirmation_interval": (
            CONFIG["switch_confirmation_interval"]
        ),
        "switch_cooldown": CONFIG["switch_cooldown"],
        "sync_retry_count": CONFIG["sync_retry_count"],
        "sync_retry_delay": CONFIG["sync_retry_delay"],
        "event_log_max_bytes": CONFIG["event_log_max_bytes"],
        "event_log_backup_count": (
            CONFIG["event_log_backup_count"]
        ),
        "fluidd_integration": CONFIG["fluidd_integration"],
        "config_file": CONFIG_FILE,
    }


CONFIG = load_config()

MOONRAKER = CONFIG["moonraker_url"]
LISTEN_HOST = CONFIG["listen_host"]
PORT = CONFIG["listen_port"]
SLOT_COUNT = CONFIG["slot_count"]
POLL_INTERVAL = CONFIG["poll_interval"]
HTTP_TIMEOUT = CONFIG["http_timeout"]
SPOOLMAN_PROXY_TIMEOUT = CONFIG["spoolman_proxy_timeout"]
SWITCH_CONFIRMATION_READS = CONFIG["switch_confirmation_reads"]
SWITCH_CONFIRMATION_INTERVAL = CONFIG[
    "switch_confirmation_interval"
]
SWITCH_COOLDOWN = CONFIG["switch_cooldown"]
SYNC_RETRY_COUNT = CONFIG["sync_retry_count"]
SYNC_RETRY_DELAY = CONFIG["sync_retry_delay"]
EVENT_LOG_MAX_BYTES = CONFIG["event_log_max_bytes"]
EVENT_LOG_BACKUP_COUNT = CONFIG["event_log_backup_count"]
FLUIDD_INTEGRATION = CONFIG["fluidd_integration"]


lock = threading.RLock()
state = {
    "active_slot": None,
    "moonraker_spool_id": None,
    "spoolman_connected": False,
    "last_error": None,
    "last_switch": None,
}
assignments = {"1": None, "2": None, "3": None, "4": None}

HTML = r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>AD5X IFS Plugin for Spoolman</title>

<style>
:root {
  font-family: Inter, Roboto, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;

  --bg: #0b1120;
  --glow: rgba(37, 99, 235, .16);
  --surface: rgba(17, 24, 39, .91);
  --surface2: #172033;
  --surface3: #1f2937;
  --border: rgba(148, 163, 184, .18);
  --border2: rgba(148, 163, 184, .32);
  --text: #eef2ff;
  --muted: #94a3b8;
  --primary: #3b82f6;
  --primary2: #2563eb;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --shadow: 0 18px 55px rgba(0, 0, 0, .28);
}

@media (prefers-color-scheme: light) {
  :root {
    --bg: #f1f5f9;
    --glow: rgba(37, 99, 235, .10);
    --surface: rgba(255, 255, 255, .94);
    --surface2: #f8fafc;
    --surface3: #eef2f7;
    --border: rgba(15, 23, 42, .10);
    --border2: rgba(15, 23, 42, .20);
    --text: #172033;
    --muted: #64748b;
    --shadow: 0 18px 45px rgba(15, 23, 42, .10);
  }
}

* {
  box-sizing: border-box;
}

html {
  min-height: 100%;
  background: var(--bg);
}

body {
  min-height: 100vh;
  margin: 0;
  color: var(--text);
  background:
    radial-gradient(circle at 15% 0%, var(--glow), transparent 34rem),
    var(--bg);
}

button,
input,
select {
  font: inherit;
}

button {
  -webkit-tap-highlight-color: transparent;
}

.app {
  width: min(1240px, 100%);
  margin: 0 auto;
  padding:
    max(22px, env(safe-area-inset-top))
    max(18px, env(safe-area-inset-right))
    max(34px, env(safe-area-inset-bottom))
    max(18px, env(safe-area-inset-left));
}

.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 15px;
}

.logo {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 54px;
  height: 54px;
  border: 1px solid rgba(96, 165, 250, .35);
  border-radius: 17px;
  background: linear-gradient(
    145deg,
    rgba(59, 130, 246, .29),
    rgba(37, 99, 235, .09)
  );
  box-shadow: inset 0 1px rgba(255, 255, 255, .08);
}

.logo svg {
  width: 32px;
  height: 32px;
  fill: var(--primary);
}

h1 {
  margin: 0;
  font-size: clamp(26px, 4vw, 37px);
  line-height: 1.08;
  letter-spacing: -.035em;
}

.subtitle {
  max-width: 720px;
  margin-top: 7px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
}

.version-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  margin-top: 9px;
  padding: 0 9px;
  border: 1px solid rgba(59, 130, 246, .28);
  border-radius: 999px;
  background: rgba(59, 130, 246, .10);
  color: #60a5fa;
  font-size: 11px;
  font-weight: 850;
  letter-spacing: .04em;
}

.connection {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex: 0 0 auto;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .10);
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

.connection-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, .13);
}

.connection.online .connection-dot {
  background: var(--success);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, .13);
}

.connection.offline .connection-dot {
  background: var(--danger);
  box-shadow: 0 0 0 4px rgba(239, 68, 68, .13);
}

.summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  min-width: 0;
  padding: 15px 17px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .08);
  backdrop-filter: blur(18px);
}

.summary-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.summary-value {
  margin-top: 7px;
  overflow: hidden;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar {
  position: sticky;
  top: 10px;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  padding: 11px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: var(--shadow);
  backdrop-filter: blur(22px);
}

.search-wrap {
  position: relative;
  flex: 1 1 300px;
}

.search-count {
  position: absolute;
  right: 12px;
  top: 50%;
  max-width: 150px;
  transform: translateY(-50%);
  overflow: hidden;
  color: var(--muted);
  font-size: 11px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
}

.search-icon {
  position: absolute;
  top: 50%;
  left: 13px;
  width: 18px;
  height: 18px;
  transform: translateY(-50%);
  fill: var(--muted);
  pointer-events: none;
}

.search {
  width: 100%;
  height: 42px;
  padding: 0 132px 0 42px;
  border: 1px solid var(--border);
  border-radius: 11px;
  outline: none;
  background: var(--surface2);
  color: var(--text);
}

.search:focus,
.select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, .15);
}

.search::placeholder {
  color: var(--muted);
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 15px;
  border: 1px solid transparent;
  border-radius: 11px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
  transition: transform .12s ease, background .15s ease, opacity .15s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:active:not(:disabled) {
  transform: translateY(0);
}

.btn:disabled {
  cursor: default;
  opacity: .43;
}

.btn-primary {
  background: var(--primary);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary2);
}

.btn-secondary {
  border-color: var(--border2);
  background: var(--surface3);
  color: var(--text);
}

.btn-ghost {
  border-color: var(--border);
  background: transparent;
  color: var(--muted);
}

.btn svg {
  width: 17px;
  height: 17px;
  fill: currentColor;
}

.unsaved {
  display: none;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
  padding: 10px 13px;
  border: 1px solid rgba(245, 158, 11, .32);
  border-radius: 12px;
  background: rgba(245, 158, 11, .09);
  color: var(--warning);
  font-size: 13px;
  font-weight: 700;
}

.unsaved.visible {
  display: flex;
}

.slots-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.slot-card {
  position: relative;
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 22px;
  background: var(--surface);
  box-shadow: 0 12px 34px rgba(0, 0, 0, .10);
  backdrop-filter: blur(18px);
  transition: border-color .18s ease, transform .18s ease,
    box-shadow .18s ease;
}

.slot-card:hover {
  transform: translateY(-2px);
  border-color: var(--border2);
}

.slot-card.active {
  border-color: rgba(34, 197, 94, .64);
  box-shadow:
    0 0 0 1px rgba(34, 197, 94, .16),
    0 18px 44px rgba(0, 0, 0, .14);
}

.slot-card.changed::after {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--warning);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, .12);
  content: "";
}

.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 15px;
}

.slot-title-wrap {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 11px;
}

.slot-number {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface2);
  font-weight: 900;
}

.slot-card.active .slot-number {
  border-color: rgba(34, 197, 94, .45);
  background: rgba(34, 197, 94, .12);
  color: var(--success);
}

.slot-name {
  font-size: 17px;
  font-weight: 850;
}

.slot-state {
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
}

.active-badge {
  display: none;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border: 1px solid rgba(34, 197, 94, .28);
  border-radius: 999px;
  background: rgba(34, 197, 94, .10);
  color: var(--success);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: .04em;
  text-transform: uppercase;
}

.slot-card.active .active-badge {
  display: inline-flex;
}

.preview {
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr);
  gap: 16px;
  min-height: 106px;
  margin-bottom: 15px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface2);
}

.spool {
  position: relative;
  display: grid;
  place-items: center;
  width: 78px;
  height: 78px;
  border: 1px solid rgba(148, 163, 184, .30);
  border-radius: 50%;
  background:
    radial-gradient(
      circle,
      var(--surface2) 0 18%,
      transparent 19% 55%,
      rgba(255, 255, 255, .13) 56% 64%,
      transparent 65% 100%
    ),
    var(--spool-background, #64748b);
  box-shadow:
    inset 0 0 0 8px rgba(255, 255, 255, .05),
    0 8px 20px rgba(0, 0, 0, .13);
}

.spool::after {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(148, 163, 184, .36);
  border-radius: 50%;
  background: var(--surface2);
  content: "";
}

.spool.empty {
  opacity: .38;
  filter: grayscale(1);
}

.filament-info {
  min-width: 0;
  align-self: center;
}

.filament-name {
  display: -webkit-box;
  min-height: 39px;
  overflow: hidden;
  font-size: 15px;
  font-weight: 850;
  line-height: 1.3;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.filament-vendor {
  margin-top: 4px;
  overflow: hidden;
  color: var(--muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  font-size: 11px;
  font-weight: 750;
}

.weight {
  margin-top: 12px;
}

.weight-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}

.weight-value {
  color: var(--text);
  font-weight: 800;
}

.progress {
  height: 7px;
  margin-top: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, .16);
}

.progress-value {
  height: 100%;
  width: 0;
  border-radius: inherit;
  background: var(--progress-background, var(--primary));
  transition: width .2s ease;
}

.slot-card.low-stock,
.slot-card.critical-stock {
  border-color: var(--border);
}

.slot-card.active.low-stock,
.slot-card.active.critical-stock {
  border-color: rgba(34, 197, 94, .64);
  box-shadow:
    0 0 0 1px rgba(34, 197, 94, .16),
    0 18px 44px rgba(0, 0, 0, .14);
}

.stock-percent {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  margin-left: 9px;
  padding: 0 7px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  font-size: 11px;
  font-weight: 850;
  vertical-align: middle;
}

.stock-percent.low {
  border-color: rgba(245, 158, 11, .30);
  background: rgba(245, 158, 11, .09);
  color: var(--warning);
}

.stock-percent.critical {
  border-color: rgba(239, 68, 68, .34);
  background: rgba(239, 68, 68, .10);
  color: var(--danger);
}

.stock-warning {
  display: none;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--warning);
  font-size: 11px;
  font-weight: 800;
}

.stock-warning.visible {
  display: flex;
}

.stock-warning.critical {
  color: var(--danger);
}

.multicolor-pill {
  color: #c4b5fd;
  border-color: rgba(139, 92, 246, .32);
  background: rgba(139, 92, 246, .10);
}

.color-count-pill {
  color: #93c5fd;
  border-color: rgba(59, 130, 246, .30);
  background: rgba(59, 130, 246, .09);
}

.empty-message {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}

.empty-message strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text);
  font-size: 14px;
}

.preview.empty-preview {
  min-height: 96px;
  opacity: .82;
}

.preview.empty-preview .spool {
  width: 66px;
  height: 66px;
}

.field-label {
  display: block;
  margin: 0 0 7px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.select {
  width: 100%;
  height: 44px;
  padding: 0 42px 0 13px;
  border: 1px solid var(--border);
  border-radius: 11px;
  outline: none;
  background-color: var(--surface2);
  color: var(--text);
  cursor: pointer;
}

.diagnostics {
  margin-top: 18px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--surface);
  overflow: hidden;
}

.diagnostics summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 16px;
  cursor: pointer;
  color: var(--muted);
  font-size: 13px;
  font-weight: 800;
  list-style: none;
}

.diagnostics summary::-webkit-details-marker {
  display: none;
}

.diagnostics-body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px 20px;
  padding: 0 16px 16px;
  color: var(--muted);
  font-size: 12px;
}

.diag-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.diag-item span:last-child {
  overflow: hidden;
  color: var(--text);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toast-stack {
  position: fixed;
  right: max(18px, env(safe-area-inset-right));
  bottom: max(18px, env(safe-area-inset-bottom));
  z-index: 100;
  display: grid;
  width: min(390px, calc(100vw - 36px));
  gap: 10px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 13px 14px;
  border: 1px solid var(--border2);
  border-radius: 13px;
  background: var(--surface);
  box-shadow: var(--shadow);
  animation: toast-in .20s ease both;
  backdrop-filter: blur(22px);
}

.toast.success {
  border-color: rgba(34, 197, 94, .42);
}

.toast.error {
  border-color: rgba(239, 68, 68, .48);
}

.toast-icon {
  flex: 0 0 auto;
  font-weight: 900;
}

.toast.success .toast-icon {
  color: var(--success);
}

.toast.error .toast-icon {
  color: var(--danger);
}

.toast-title {
  font-size: 13px;
  font-weight: 850;
}

.toast-message {
  margin-top: 3px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.45;
}

.loading {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: none;
  place-items: center;
  background: rgba(2, 6, 23, .38);
  backdrop-filter: blur(4px);
}

.loading.visible {
  display: grid;
}

.loader {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 15px;
  background: var(--surface);
  box-shadow: var(--shadow);
  font-size: 13px;
  font-weight: 800;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 3px solid rgba(148, 163, 184, .25);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin .75s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 860px) {
  .hero {
    flex-direction: column;
  }

  .summary {
    grid-template-columns: 1fr;
  }

  .slots-grid {
    grid-template-columns: 1fr;
  }

  .toolbar {
    position: static;
    flex-wrap: wrap;
  }

  .search-wrap {
    flex-basis: 100%;
  }

  .actions {
    width: 100%;
  }

  .actions .btn {
    flex: 1;
  }
}

@media (max-width: 560px) {
  .app {
    padding-left: 12px;
    padding-right: 12px;
  }

  .logo {
    width: 47px;
    height: 47px;
  }

  .toolbar {
    padding: 9px;
  }

  .actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .btn-primary {
    grid-column: 1 / -1;
  }

  .slot-card {
    padding: 14px;
    border-radius: 18px;
  }

  .preview {
    grid-template-columns: 60px minmax(0, 1fr);
    gap: 11px;
    padding: 12px;
  }

  .spool {
    width: 60px;
    height: 60px;
  }

  .filament-name {
    font-size: 14px;
  }

  .meta {
    gap: 5px;
  }

  .pill {
    min-height: 22px;
    padding: 0 7px;
  }

  .diagnostics-body {
    grid-template-columns: 1fr;
  }
}
</style>
</head>

<body>
<div class="app">
  <header class="hero">
    <div class="brand">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2a8 8 0 0 1 7.75 6H16.9a5 5 0 0 0-9.8 0H4.25A8 8 0 0 1 12 4zm0 5a3 3 0 1 1 0 6 3 3 0 0 1 0-6zm0 11a8 8 0 0 1-7.75-6H7.1a5 5 0 0 0 9.8 0h2.85A8 8 0 0 1 12 20z"/>
        </svg>
      </div>

      <div>
        <h1>AD5X IFS Plugin for Spoolman</h1>
        <div class="subtitle">
          Привязка физических каналов IFS к катушкам Spoolman
          и автоматическая синхронизация активного филамента.
        </div>
        <div class="version-badge">v0.2.2 beta</div>
      </div>
    </div>

    <div class="connection" id="connection">
      <span class="connection-dot"></span>
      <span id="connectionText">Подключение…</span>
    </div>
  </header>

  <section class="summary">
    <div class="summary-card">
      <div class="summary-label">Активный слот IFS</div>
      <div class="summary-value" id="summarySlot">—</div>
    </div>

    <div class="summary-card">
      <div class="summary-label">Катушка Moonraker</div>
      <div class="summary-value" id="summarySpool">—</div>
    </div>

    <div class="summary-card">
      <div class="summary-label">Назначено слотов</div>
      <div class="summary-value" id="summaryAssigned">—</div>
    </div>
  </section>

  <section class="toolbar">
    <div class="search-wrap">
      <svg class="search-icon" viewBox="0 0 24 24">
        <path d="M9.5 3a6.5 6.5 0 1 0 3.98 11.64L19.85 21 21 19.85l-6.36-6.37A6.5 6.5 0 0 0 9.5 3zm0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z"/>
      </svg>

      <input
        class="search"
        id="searchInput"
        type="search"
        placeholder="Поиск по ID, производителю, названию или материалу"
        autocomplete="off"
      >
      <span class="search-count" id="searchCount">Катушек: —</span>
    </div>

    <div class="actions">
      <button class="btn btn-ghost" id="refreshButton" type="button">
        <svg viewBox="0 0 24 24">
          <path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.1A6 6 0 1 1 16.22 7.78L13 11h7V4l-2.35 2.35z"/>
        </svg>
        Обновить
      </button>

      <button class="btn btn-secondary" id="resetButton" type="button" disabled>
        Отменить
      </button>

      <button class="btn btn-secondary" id="syncButton" type="button">
        Синхронизировать
      </button>

      <button class="btn btn-primary" id="saveButton" type="button" disabled>
        Сохранить изменения
      </button>
    </div>
  </section>

  <div class="unsaved" id="unsavedBanner">
    <span>●</span>
    Есть несохранённые изменения
  </div>

  <main class="slots-grid" id="slotsGrid"></main>

  <details class="diagnostics">
    <summary>
      <span>Диагностика</span>
      <span>Показать сведения</span>
    </summary>

    <div class="diagnostics-body">
      <div class="diag-item">
        <span>Активный слот</span>
        <span id="diagSlot">—</span>
      </div>

      <div class="diag-item">
        <span>Spool ID Moonraker</span>
        <span id="diagSpool">—</span>
      </div>

      <div class="diag-item">
        <span>Связь со Spoolman</span>
        <span id="diagConnection">—</span>
      </div>

      <div class="diag-item">
        <span>Последняя синхронизация</span>
        <span id="diagSwitch">—</span>
      </div>

      <div class="diag-item">
        <span>Последняя ошибка</span>
        <span id="diagError">Нет</span>
      </div>

      <div class="diag-item">
        <span>Версия интерфейса</span>
        <span>0.2.2 beta</span>
      </div>
    </div>
  </details>
</div>

<div class="toast-stack" id="toastStack"></div>

<div class="loading visible" id="loading">
  <div class="loader">
    <span class="spinner"></span>
    <span id="loadingText">Загрузка данных…</span>
  </div>
</div>

<script>
"use strict";

const SLOT_COUNT = 4;

let spools = [];
let statusData = null;
let originalAssignments = {};
let draftAssignments = {};
let searchQuery = "";
let requestInProgress = false;

const el = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options
  });

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(`Некорректный ответ сервера: HTTP ${response.status}`);
  }

  if (!response.ok) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }

  return data;
}

function setLoading(visible, text = "Загрузка данных…") {
  el("loadingText").textContent = text;
  el("loading").classList.toggle("visible", visible);
}

function showToast(type, title, message) {
  const toast = document.createElement("div");

  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${type === "success" ? "✓" : "!"}</div>
    <div>
      <div class="toast-title">${escapeHtml(title)}</div>
      <div class="toast-message">${escapeHtml(message)}</div>
    </div>
  `;

  el("toastStack").appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 220);
  }, 4200);
}

function normalizeAssignments(raw) {
  const result = {};

  for (let slot = 1; slot <= SLOT_COUNT; slot += 1) {
    const value = raw?.[String(slot)];

    result[String(slot)] =
      value === null || value === undefined || value === ""
        ? null
        : Number(value);
  }

  return result;
}

function assignmentsEqual(left, right) {
  for (let slot = 1; slot <= SLOT_COUNT; slot += 1) {
    const key = String(slot);

    if ((left[key] ?? null) !== (right[key] ?? null)) {
      return false;
    }
  }

  return true;
}

function hasChanges() {
  return !assignmentsEqual(originalAssignments, draftAssignments);
}

function getSpool(id) {
  if (id === null || id === undefined) {
    return null;
  }

  return spools.find(item => Number(item.id) === Number(id)) || null;
}

function filamentOf(spool) {
  return spool?.filament || {};
}

function normalizeHex(value) {
  const raw = String(value || "")
    .trim()
    .replace(/^#/, "");

  if (!/^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(raw)) {
    return null;
  }

  return `#${raw}`;
}

function filamentColors(spool) {
  const filament = filamentOf(spool);

  const multiple = String(filament.multi_color_hexes || "")
    .split(",")
    .map(normalizeHex)
    .filter(Boolean);

  if (multiple.length > 0) {
    return multiple;
  }

  const single = normalizeHex(filament.color_hex);

  return single ? [single] : ["#64748b"];
}

function multiColorDirection(spool) {
  return String(
    filamentOf(spool).multi_color_direction || ""
  ).trim().toLowerCase();
}

function directionInfo(direction) {
  const value = String(direction || "").trim().toLowerCase();

  const labels = {
    coaxial: "Коаксиальный",
    longitudinal: "Продольный",
    linear: "Смена по длине",
    gradient: "Градиентный",
    rainbow: "Радужный",
    sequential: "Последовательный",
    alternating: "Чередующийся",
    random: "Случайная смена"
  };

  const sequentialDirections = [
    "linear",
    "gradient",
    "rainbow",
    "sequential",
    "alternating",
    "random",
    "change"
  ];

  return {
    raw: value,
    label: labels[value] || (value ? value.toUpperCase() : "Многоцветный"),
    sequential: sequentialDirections.some(
      item => value === item || value.includes(item)
    )
  };
}

function sharpLinearGradient(colors) {
  const segment = 100 / colors.length;
  const stops = [];

  colors.forEach((color, index) => {
    const start = (segment * index).toFixed(3);
    const end = (segment * (index + 1)).toFixed(3);

    stops.push(`${color} ${start}%`);
    stops.push(`${color} ${end}%`);
  });

  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

function spoolVisual(spool) {
  const colors = filamentColors(spool);
  const direction = directionInfo(multiColorDirection(spool));
  const multicolor = colors.length > 1;

  if (!multicolor) {
    return {
      background: colors[0],
      progress: colors[0],
      multicolor: false,
      label: "",
      directionRaw: "",
      colorCount: 1
    };
  }

  if (direction.sequential) {
    const ringColors = [...colors, colors[0]].join(", ");

    return {
      background: `conic-gradient(from 0deg, ${ringColors})`,
      progress: `linear-gradient(90deg, ${colors.join(", ")})`,
      multicolor: true,
      label: direction.label,
      directionRaw: direction.raw,
      colorCount: colors.length
    };
  }

  const segment = 100 / colors.length;
  const sectors = colors.map((color, index) => {
    const start = (segment * index).toFixed(3);
    const end = (segment * (index + 1)).toFixed(3);

    return `${color} ${start}% ${end}%`;
  });

  return {
    background: `conic-gradient(from -90deg, ${sectors.join(", ")})`,
    progress: sharpLinearGradient(colors),
    multicolor: true,
    label: direction.label,
    directionRaw: direction.raw,
    colorCount: colors.length
  };
}

function colorCountText(count) {
  const number = Number(count);

  if (number % 10 === 1 && number % 100 !== 11) {
    return `${number} цвет`;
  }

  if (
    [2, 3, 4].includes(number % 10) &&
    ![12, 13, 14].includes(number % 100)
  ) {
    return `${number} цвета`;
  }

  return `${number} цветов`;
}

function formatWeight(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  if (number >= 1000) {
    const kg = number / 1000;
    return `${kg % 1 === 0 ? kg.toFixed(0) : kg.toFixed(2)} кг`;
  }

  return `${Math.round(number)} г`;
}

function displayName(spool) {
  if (!spool) {
    return "Не назначено";
  }

  const filament = filamentOf(spool);
  const vendor = filament.vendor?.name || "Без производителя";
  const name = filament.name || "Без названия";

  return `${vendor} · ${name}`;
}

function optionText(spool) {
  const filament = filamentOf(spool);
  const vendor = filament.vendor?.name || "Без производителя";
  const name = filament.name || "Без названия";
  const material = filament.material || "?";

  return `ID ${spool.id} — ${vendor} / ${name} / ${material} — ${formatWeight(spool.remaining_weight)}`;
}

function searchText(spool) {
  const filament = filamentOf(spool);

  return [
    spool.id,
    filament.vendor?.name,
    filament.name,
    filament.material,
    filament.color_hex
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function usedElsewhere(spoolId, currentSlot) {
  if (spoolId === null) {
    return false;
  }

  for (let slot = 1; slot <= SLOT_COUNT; slot += 1) {
    if (
      slot !== currentSlot &&
      Number(draftAssignments[String(slot)]) === Number(spoolId)
    ) {
      return true;
    }
  }

  return false;
}

function availableSpools(slot) {
  const selectedId = draftAssignments[String(slot)];

  return spools.filter(spool => {
    if (spool.archived) {
      return false;
    }

    const matches =
      !searchQuery || searchText(spool).includes(searchQuery);

    const selectable =
      Number(spool.id) === Number(selectedId) ||
      !usedElsewhere(spool.id, slot);

    return matches && selectable;
  });
}

function buildOptions(slot) {
  const selectedId = draftAssignments[String(slot)];
  const options = [`<option value="">Не назначено</option>`];
  const available = availableSpools(slot);
  const selectedSpool = getSpool(selectedId);

  if (
    selectedSpool &&
    !available.some(item => Number(item.id) === Number(selectedId))
  ) {
    options.push(
      `<option value="${selectedSpool.id}" selected>` +
      `${escapeHtml(optionText(selectedSpool))}</option>`
    );
  }

  for (const spool of available) {
    const selected =
      Number(spool.id) === Number(selectedId)
        ? " selected"
        : "";

    options.push(
      `<option value="${spool.id}"${selected}>` +
      `${escapeHtml(optionText(spool))}</option>`
    );
  }

  return options.join("");
}

function renderSlot(slot) {
  const spoolId = draftAssignments[String(slot)];
  const spool = getSpool(spoolId);
  const filament = filamentOf(spool);
  const active = Number(statusData?.active_slot) === slot;

  const changed =
    (originalAssignments[String(slot)] ?? null) !==
    (draftAssignments[String(slot)] ?? null);

  const remaining = Number(spool?.remaining_weight);
  const initial = Number(spool?.initial_weight);

  const percent =
    Number.isFinite(remaining) &&
    Number.isFinite(initial) &&
    initial > 0
      ? Math.max(0, Math.min(100, remaining / initial * 100))
      : 0;

  const vendor = filament.vendor?.name || "Катушка не выбрана";
  const name =
    filament.name || "Назначь катушку Spoolman этому слоту";

  const material = filament.material || "—";
  const visual = spoolVisual(spool);

  const percentClass =
    percent < 10
      ? " critical"
      : percent < 30
        ? " low"
        : "";

  return `
    <article
      class="slot-card${active ? " active" : ""}${changed ? " changed" : ""}"
      style="--spool-background:${escapeHtml(visual.background)};--progress-background:${escapeHtml(visual.progress)}"
    >
      <header class="slot-header">
        <div class="slot-title-wrap">
          <div class="slot-number">${slot}</div>

          <div>
            <div class="slot-name">IFS ${slot}</div>
            <div class="slot-state">
              ${active ? "Используется экструдером" : "Физический канал IFS"}
            </div>
          </div>
        </div>

        <div class="active-badge">
          <span>●</span>
          Активный
        </div>
      </header>

      <div class="preview${spool ? "" : " empty-preview"}">
        <div class="spool${spool ? "" : " empty"}"></div>

        <div class="filament-info">
          ${spool
            ? `
              <div class="filament-name" title="${escapeHtml(name)}">
                ${escapeHtml(name)}
              </div>

              <div class="filament-vendor" title="${escapeHtml(vendor)}">
                ${escapeHtml(vendor)}
              </div>
            `
            : `
              <div class="empty-message">
                <strong>Катушка не назначена</strong>
                Выбери катушку Spoolman в списке ниже.
              </div>
            `}

          <div class="meta">
            <span class="pill">${escapeHtml(material)}</span>
            <span class="pill">
              ${spool ? `ID ${spool.id}` : "Без назначения"}
            </span>
            ${visual.multicolor
              ? `
                <span
                  class="pill multicolor-pill"
                  title="Spoolman: ${escapeHtml(visual.directionRaw || "не указано")}"
                >
                  ${escapeHtml(visual.label)}
                </span>
                <span class="pill color-count-pill">
                  ${escapeHtml(colorCountText(visual.colorCount))}
                </span>
              `
              : ""}
          </div>

          <div class="weight">
            <div class="weight-line">
              <span>Остаток</span>
              <span class="weight-value">
                ${spool
                  ? `${formatWeight(remaining)} / ${formatWeight(initial)}` +
                    `<span class="stock-percent${percentClass}">${Math.round(percent)}%</span>`
                  : "—"}
              </span>
            </div>

            <div class="progress">
              <div
                class="progress-value"
                style="width:${percent.toFixed(1)}%"
              ></div>
            </div>

            ${spool && percent < 30
              ? `
                <div class="stock-warning visible${percent < 10 ? " critical" : ""}">
                  <span>●</span>
                  ${percent < 10
                    ? "Критически малый остаток"
                    : "Низкий остаток филамента"}
                </div>
              `
              : ""}
          </div>
        </div>
      </div>

      <label class="field-label" for="slotSelect${slot}">
        Катушка Spoolman
      </label>

      <select
        class="select slot-select"
        id="slotSelect${slot}"
        data-slot="${slot}"
      >
        ${buildOptions(slot)}
      </select>
    </article>
  `;
}

function renderSlots() {
  el("slotsGrid").innerHTML =
    Array.from(
      { length: SLOT_COUNT },
      (_, index) => renderSlot(index + 1)
    ).join("");

  document.querySelectorAll(".slot-select").forEach(select => {
    select.addEventListener("change", event => {
      const slot = Number(event.currentTarget.dataset.slot);
      const value = event.currentTarget.value;

      draftAssignments[String(slot)] =
        value === "" ? null : Number(value);

      renderAll();
    });
  });
}

function renderSummary() {
  const activeSlot = statusData?.active_slot;
  const activeSpool = getSpool(statusData?.moonraker_spool_id);

  el("summarySlot").textContent =
    activeSlot ? `IFS ${activeSlot}` : "Не определён";

  el("summarySpool").textContent =
    activeSpool
      ? displayName(activeSpool)
      : statusData?.moonraker_spool_id
        ? `ID ${statusData.moonraker_spool_id}`
        : "Не выбрана";

  const assignedCount = Object.values(draftAssignments)
    .filter(value => value !== null)
    .length;

  el("summaryAssigned").textContent =
    `${assignedCount} из ${SLOT_COUNT}`;
}

function renderConnection() {
  const connected = Boolean(statusData?.spoolman_connected);
  const node = el("connection");

  node.classList.toggle("online", connected);
  node.classList.toggle("offline", !connected);

  el("connectionText").textContent =
    connected ? "Spoolman подключён" : "Нет связи со Spoolman";
}

function renderDiagnostics() {
  el("diagSlot").textContent =
    statusData?.active_slot ?? "—";

  el("diagSpool").textContent =
    statusData?.moonraker_spool_id ?? "—";

  el("diagConnection").textContent =
    statusData?.spoolman_connected ? "Подключено" : "Нет связи";

  const lastSwitch = statusData?.last_switch;

  el("diagSwitch").textContent =
    lastSwitch
      ? `${lastSwitch.time} · IFS ${lastSwitch.slot} → ID ${lastSwitch.spool_id}`
      : "В этой сессии не выполнялась";

  el("diagError").textContent =
    statusData?.last_error || "Нет";
}

function renderSearchCount() {
  const visible = spools.filter(spool => {
    if (spool.archived) {
      return false;
    }

    return !searchQuery || searchText(spool).includes(searchQuery);
  }).length;

  el("searchCount").textContent =
    searchQuery
      ? `Найдено: ${visible}`
      : `Катушек: ${visible}`;
}

function renderChangeState() {
  const changed = hasChanges();

  el("saveButton").disabled = !changed;
  el("resetButton").disabled = !changed;
  el("unsavedBanner").classList.toggle("visible", changed);
}

function renderAll() {
  renderSummary();
  renderConnection();
  renderSlots();
  renderDiagnostics();
  renderSearchCount();
  renderChangeState();
}

async function loadData({
  showLoader = false,
  preserveDraft = false,
  notify = false
} = {}) {
  if (requestInProgress) {
    return;
  }

  requestInProgress = true;

  if (showLoader) {
    setLoading(true, "Получение данных Spoolman…");
  }

  try {
    const [newSpools, newStatus] = await Promise.all([
      api("/api/spools"),
      api("/api/status")
    ]);

    const previousDraft = { ...draftAssignments };
    const hadChanges = hasChanges();

    spools = Array.isArray(newSpools) ? newSpools : [];
    statusData = newStatus;

    originalAssignments =
      normalizeAssignments(newStatus.assignments);

    draftAssignments =
      preserveDraft && hadChanges
        ? previousDraft
        : { ...originalAssignments };

    renderAll();

    if (notify) {
      showToast(
        "success",
        "Данные обновлены",
        `Загружено катушек: ${spools.length}`
      );
    }
  } catch (error) {
    showToast(
      "error",
      "Не удалось загрузить данные",
      error instanceof Error ? error.message : String(error)
    );

    el("connection").classList.add("offline");
    el("connectionText").textContent = "Ошибка подключения";
  } finally {
    requestInProgress = false;

    if (showLoader) {
      setLoading(false);
    }
  }
}

async function saveAssignments() {
  if (!hasChanges()) {
    return;
  }

  const changedSlots = [];

  for (let slot = 1; slot <= SLOT_COUNT; slot += 1) {
    const key = String(slot);

    if (
      (originalAssignments[key] ?? null) !==
      (draftAssignments[key] ?? null)
    ) {
      changedSlots.push(slot);
    }
  }

  const activeSlot = Number(statusData?.active_slot);

  if (
    changedSlots.includes(activeSlot) &&
    draftAssignments[String(activeSlot)] === null
  ) {
    const confirmed = window.confirm(
      `Активный слот IFS ${activeSlot} останется без катушки Spoolman. ` +
      `Moonraker не сможет синхронизировать текущую катушку. Продолжить?`
    );

    if (!confirmed) {
      return;
    }
  }

  setLoading(true, "Сохранение назначений…");

  try {
    for (const slot of changedSlots) {
      await api("/api/assign", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          slot,
          spool_id: draftAssignments[String(slot)]
        })
      });
    }

    await loadData();

    showToast(
      "success",
      "Изменения сохранены",
      `Обновлено слотов: ${changedSlots.length}`
    );
  } catch (error) {
    showToast(
      "error",
      "Ошибка сохранения",
      error instanceof Error ? error.message : String(error)
    );

    await loadData({
      preserveDraft: true
    });
  } finally {
    setLoading(false);
  }
}

async function synchronize() {
  setLoading(true, "Синхронизация активного слота…");

  try {
    await api("/api/sync", {
      method: "POST"
    });

    await loadData({
      preserveDraft: true
    });

    showToast(
      "success",
      "Синхронизация выполнена",
      "Активный слот сопоставлен с катушкой Spoolman"
    );
  } catch (error) {
    showToast(
      "error",
      "Ошибка синхронизации",
      error instanceof Error ? error.message : String(error)
    );
  } finally {
    setLoading(false);
  }
}

el("searchInput").addEventListener("input", event => {
  searchQuery = event.currentTarget.value.trim().toLowerCase();
  renderSlots();
  renderSearchCount();
});

el("refreshButton").addEventListener("click", () => {
  loadData({
    showLoader: true,
    preserveDraft: true,
    notify: true
  });
});

el("resetButton").addEventListener("click", () => {
  draftAssignments = { ...originalAssignments };
  renderAll();

  showToast(
    "success",
    "Изменения отменены",
    "Восстановлены последние сохранённые назначения"
  );
});

el("saveButton").addEventListener("click", saveAssignments);
el("syncButton").addEventListener("click", synchronize);

window.addEventListener("beforeunload", event => {
  if (!hasChanges()) {
    return;
  }

  event.preventDefault();
  event.returnValue = "";
});

loadData({
  showLoader: true
});

setInterval(() => {
  loadData({
    preserveDraft: true
  });
}, 5000);
</script>
</body>
</html>
'''

def atomic_write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def load_assignments():
    global assignments
    try:
        with open(ASSIGNMENTS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        assignments = {str(i): (int(raw.get(str(i))) if raw.get(str(i)) not in (None, "", 0, "0") else None) for i in range(1,5)}
    except FileNotFoundError:
        atomic_write_json(ASSIGNMENTS_FILE, assignments)
    except Exception as exc:
        state["last_error"] = f"assignments.json: {exc}"

def http_json(url, method="GET", payload=None, timeout=HTTP_TIMEOUT):
    data = None; headers = {"Accept":"application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8"); headers["Content-Type"]="application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8")) if body else {}



# AD5X_IFS_DIAGNOSTICS_V0_5

EVENT_LOG_FILE = os.path.join(APP_DIR, "events.log")

os.makedirs(APP_DIR, exist_ok=True)

event_logger = logging.getLogger("ad5x_ifs_plugin")
event_logger.setLevel(logging.INFO)
event_logger.propagate = False

if not event_logger.handlers:
    event_handler = RotatingFileHandler(
        EVENT_LOG_FILE,
        maxBytes=EVENT_LOG_MAX_BYTES,
        backupCount=EVENT_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    event_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    event_logger.addHandler(event_handler)


_diagnostics_runtime = {
    "started_monotonic": time.monotonic(),
    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "last_sensor_read_at": None,
    "last_slot_confirmed_at": None,
    "last_sync_attempt_at": None,
    "last_sync_success_at": None,
    "sensor_invalid_active": False,
}


def timestamp_now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def increment_state(name, amount=1):
    with lock:
        state[name] = int(state.get(name, 0)) + amount
        return state[name]


def event_log(level, event, message, **fields):
    payload = {
        "event": event,
        "message": message,
    }

    payload.update(fields)

    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    log_method = getattr(
        event_logger,
        str(level).lower(),
        event_logger.info,
    )

    log_method(rendered)


def state_snapshot():
    with lock:
        return dict(state)


def build_health():
    snapshot = state_snapshot()
    now_monotonic = time.monotonic()

    last_sensor_monotonic = snapshot.get(
        "last_sensor_read_monotonic"
    )

    sensor_age = None

    if isinstance(last_sensor_monotonic, (int, float)):
        sensor_age = max(
            0.0,
            now_monotonic - last_sensor_monotonic,
        )

    sensor_ok = (
        snapshot.get("raw_active_slot") is not None
        and sensor_age is not None
        and sensor_age <= max(5.0, POLL_INTERVAL * 4)
    )

    moonraker_ok = (
        snapshot.get("moonraker_status_ok") is True
    )

    spoolman_ok = bool(
        snapshot.get("spoolman_connected")
    )

    last_error = snapshot.get("last_error")

    if (
        sensor_ok
        and moonraker_ok
        and spoolman_ok
        and not last_error
    ):
        overall = "ok"
    elif sensor_ok and moonraker_ok:
        overall = "degraded"
    else:
        overall = "error"

    return {
        "application": "AD5X IFS Plugin for Spoolman",
        "version": APP_VERSION,
        "status": overall,
        "uptime_seconds": round(
            now_monotonic
            - _diagnostics_runtime["started_monotonic"],
            1,
        ),
        "started_at": _diagnostics_runtime["started_at"],
        "components": {
            "ifs_sensor": {
                "ok": sensor_ok,
                "raw_slot": snapshot.get("raw_active_slot"),
                "confirmed_slot": snapshot.get(
                    "confirmed_active_slot"
                ),
                "last_read_at": (
                    _diagnostics_runtime[
                        "last_sensor_read_at"
                    ]
                ),
                "age_seconds": (
                    None
                    if sensor_age is None
                    else round(sensor_age, 2)
                ),
                "invalid_reads": snapshot.get(
                    "invalid_sensor_reads",
                    0,
                ),
            },
            "moonraker": {
                "ok": moonraker_ok,
                "url": MOONRAKER,
                "spool_id": snapshot.get(
                    "moonraker_spool_id"
                ),
            },
            "spoolman": {
                "ok": spoolman_ok,
                "connected": spoolman_ok,
            },
        },
        "synchronization": {
            "desired_spool_id": snapshot.get(
                "desired_spool_id"
            ),
            "last_result": snapshot.get(
                "last_sync_result"
            ),
            "last_reason": snapshot.get(
                "last_sync_reason"
            ),
            "last_attempt_at": (
                _diagnostics_runtime[
                    "last_sync_attempt_at"
                ]
            ),
            "last_success_at": (
                _diagnostics_runtime[
                    "last_sync_success_at"
                ]
            ),
            "last_slot_confirmed_at": (
                _diagnostics_runtime[
                    "last_slot_confirmed_at"
                ]
            ),
            "last_switch": snapshot.get("last_switch"),
        },
        "counters": {
            "successful_switches": snapshot.get(
                "successful_switches",
                0,
            ),
            "skipped_switches": snapshot.get(
                "skipped_switches",
                0,
            ),
            "failed_syncs": snapshot.get(
                "failed_syncs",
                0,
            ),
            "invalid_sensor_reads": snapshot.get(
                "invalid_sensor_reads",
                0,
            ),
        },
        "last_error": last_error,
        "event_log": EVENT_LOG_FILE,
    }

# AD5X_IFS_SYNC_RELIABILITY_V0_4

_sync_runtime = {
    "last_switch_monotonic": 0.0,
}


def set_state(**values):
    with lock:
        state.update(values)


def confirmation_snapshot(values):
    return {
        "required": SWITCH_CONFIRMATION_READS,
        "values": values,
        "confirmed": (
            values[0]
            if (
                len(values) == SWITCH_CONFIRMATION_READS
                and len(set(values)) == 1
                and values[0] is not None
            )
            else None
        ),
    }


def confirm_active_slot(first_value=None):
    values = []

    for index in range(SWITCH_CONFIRMATION_READS):
        if index == 0 and first_value is not None:
            value = first_value
        else:
            value = read_active_slot()

        values.append(value)

        set_state(
            raw_active_slot=value,
            candidate_slot=value,
            candidate_reads=index + 1,
            confirmation_values=list(values),
        )

        if value is None:
            return None, values

        if len(values) > 1 and value != values[0]:
            return None, values

        if index + 1 < SWITCH_CONFIRMATION_READS:
            time.sleep(SWITCH_CONFIRMATION_INTERVAL)

    return values[0], values


def desired_spool_for_slot(slot):
    if slot is None:
        return None

    with lock:
        value = assignments.get(str(slot))

    return None if value is None else int(value)


def wait_for_switch_cooldown():
    elapsed = (
        time.monotonic()
        - _sync_runtime["last_switch_monotonic"]
    )

    remaining = SWITCH_COOLDOWN - elapsed

    if remaining > 0:
        set_state(
            last_sync_reason="switch_cooldown",
            cooldown_remaining=round(remaining, 3),
        )
        time.sleep(remaining)

    set_state(cooldown_remaining=0.0)



def read_active_slot():
    with open(FF_CONFIG, "r", encoding="utf-8") as stream:
        config = json.load(stream)

    value = config.get("FFMInfo", {}).get("channel")

    if value is None:
        return None

    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    return value if 1 <= value <= SLOT_COUNT else None


def get_moonraker_status():
    return http_json(MOONRAKER + "/server/spoolman/status").get("result", {})

def set_active_spool(spool_id):
    return http_json(MOONRAKER + "/server/spoolman/spool_id", method="POST", payload={"spool_id": spool_id}).get("result", {}).get("spool_id")

def list_spools():
    payload={"use_v2_response":True,"request_method":"GET","path":"/v1/spool"}
    result=http_json(MOONRAKER+"/server/spoolman/proxy",method="POST",payload=payload,timeout=SPOOLMAN_PROXY_TIMEOUT).get("result",{})
    if result.get("error"): raise RuntimeError(result["error"].get("message",str(result["error"])))
    response=result.get("response",[])
    if not isinstance(response,list): raise RuntimeError("Spoolman вернул неожиданный формат списка катушек")
    return [s for s in response if not s.get("archived",False)]



def synchronize(
    force=False,
    slot=None,
    reason="manual",
):
    if slot is None:
        raw_slot = read_active_slot()
        slot, confirmation_values = confirm_active_slot(
            raw_slot
        )

        if slot is None:
            set_state(
                last_sync_reason="slot_not_confirmed",
                confirmation_values=confirmation_values,
            )

            event_log(
                "warning",
                "slot_not_confirmed",
                "Активный слот IFS не подтверждён",
                values=confirmation_values,
                force=force,
            )

            if force:
                raise RuntimeError(
                    "Активный слот IFS не подтверждён"
                )

            return False

    desired = desired_spool_for_slot(slot)

    set_state(
        active_slot=slot,
        confirmed_active_slot=slot,
        desired_spool_id=desired,
        last_sync_reason=reason,
    )

    if desired is None:
        set_state(
            last_sync_reason="slot_has_no_assignment",
            last_sync_result="skipped",
        )

        event_log(
            "warning",
            "slot_without_assignment",
            "Активному слоту не назначена катушка",
            slot=slot,
            reason=reason,
        )

        return False

    last_exception = None

    for attempt in range(1, SYNC_RETRY_COUNT + 1):
        _diagnostics_runtime[
            "last_sync_attempt_at"
        ] = timestamp_now()

        set_state(
            sync_attempt=attempt,
            sync_attempts_total=SYNC_RETRY_COUNT,
        )

        event_log(
            "info",
            "sync_attempt",
            "Проверка синхронизации",
            slot=slot,
            desired_spool_id=desired,
            attempt=attempt,
            attempts_total=SYNC_RETRY_COUNT,
            reason=reason,
            force=force,
        )

        try:
            moonraker = get_moonraker_status()

            connected = bool(
                moonraker.get("spoolman_connected")
            )

            current = moonraker.get("spool_id")

            if current is not None:
                current = int(current)

            set_state(
                moonraker_status_ok=True,
                spoolman_connected=connected,
                moonraker_spool_id=current,
            )

            if not connected:
                raise RuntimeError(
                    "Moonraker сообщает об отсутствии связи "
                    "со Spoolman"
                )

            if current == desired and not force:
                increment_state("skipped_switches")

                _diagnostics_runtime[
                    "last_sync_success_at"
                ] = timestamp_now()

                set_state(
                    last_error=None,
                    last_sync_result="already_active",
                    last_sync_reason=reason,
                )

                event_log(
                    "info",
                    "switch_skipped",
                    "Нужная катушка уже активна",
                    slot=slot,
                    spool_id=desired,
                    reason=reason,
                )

                return False

            wait_for_switch_cooldown()

            actual = set_active_spool(desired)

            if actual is not None:
                actual = int(actual)

            if actual != desired:
                raise RuntimeError(
                    "Moonraker вернул неожиданный spool ID: "
                    f"{actual!r}, ожидался {desired}"
                )

            now_text = timestamp_now()

            _sync_runtime["last_switch_monotonic"] = (
                time.monotonic()
            )

            _diagnostics_runtime[
                "last_sync_success_at"
            ] = now_text

            increment_state("successful_switches")

            set_state(
                moonraker_status_ok=True,
                moonraker_spool_id=actual,
                last_error=None,
                last_sync_result="switched",
                last_sync_reason=reason,
                last_switch={
                    "time": now_text,
                    "slot": slot,
                    "spool_id": actual,
                    "reason": reason,
                    "attempt": attempt,
                },
            )

            event_log(
                "info",
                "spool_switched",
                "Активная катушка Moonraker изменена",
                slot=slot,
                previous_spool_id=current,
                spool_id=actual,
                reason=reason,
                attempt=attempt,
            )

            return True

        except Exception as exc:
            last_exception = exc

            set_state(
                moonraker_status_ok=False,
                last_error=str(exc),
                last_sync_result="retrying",
                last_sync_reason=reason,
            )

            event_log(
                "warning",
                "sync_attempt_failed",
                "Попытка синхронизации завершилась ошибкой",
                slot=slot,
                desired_spool_id=desired,
                attempt=attempt,
                attempts_total=SYNC_RETRY_COUNT,
                reason=reason,
                error=str(exc),
            )

            if attempt < SYNC_RETRY_COUNT:
                time.sleep(SYNC_RETRY_DELAY)

    increment_state("failed_syncs")
    set_state(last_sync_result="failed")

    event_log(
        "error",
        "sync_failed",
        "Синхронизация не выполнена",
        slot=slot,
        desired_spool_id=desired,
        attempts=SYNC_RETRY_COUNT,
        reason=reason,
        error=str(last_exception),
    )

    raise RuntimeError(
        f"Синхронизация не выполнена после "
        f"{SYNC_RETRY_COUNT} попыток: {last_exception}"
    )





def monitor():
    confirmed_slot = None

    set_state(
        raw_active_slot=None,
        candidate_slot=None,
        candidate_reads=0,
        confirmation_values=[],
        confirmed_active_slot=None,
        desired_spool_id=None,
        moonraker_status_ok=False,
        last_sync_reason="startup",
        last_sync_result="waiting",
        sync_attempt=0,
        sync_attempts_total=SYNC_RETRY_COUNT,
        successful_switches=0,
        skipped_switches=0,
        failed_syncs=0,
        invalid_sensor_reads=0,
        cooldown_remaining=0.0,
        last_sensor_read_monotonic=None,
    )

    event_log(
        "info",
        "monitor_started",
        "Мониторинг активного слота IFS запущен",
        poll_interval=POLL_INTERVAL,
        confirmation_reads=SWITCH_CONFIRMATION_READS,
        confirmation_interval=(
            SWITCH_CONFIRMATION_INTERVAL
        ),
    )

    while True:
        try:
            raw_slot = read_active_slot()
            now_monotonic = time.monotonic()
            now_text = timestamp_now()

            _diagnostics_runtime[
                "last_sensor_read_at"
            ] = now_text

            set_state(
                raw_active_slot=raw_slot,
                last_sensor_read_monotonic=now_monotonic,
            )

            if raw_slot is None:
                increment_state("invalid_sensor_reads")

                set_state(
                    candidate_slot=None,
                    candidate_reads=0,
                    confirmation_values=[],
                    last_sync_reason="invalid_sensor_value",
                )

                if not _diagnostics_runtime[
                    "sensor_invalid_active"
                ]:
                    _diagnostics_runtime[
                        "sensor_invalid_active"
                    ] = True

                    event_log(
                        "warning",
                        "sensor_value_invalid",
                        "Датчик IFS вернул некорректный канал",
                    )

                time.sleep(POLL_INTERVAL)
                continue

            if _diagnostics_runtime[
                "sensor_invalid_active"
            ]:
                _diagnostics_runtime[
                    "sensor_invalid_active"
                ] = False

                event_log(
                    "info",
                    "sensor_recovered",
                    "Корректное чтение канала IFS восстановлено",
                    raw_slot=raw_slot,
                )

            if raw_slot != confirmed_slot:
                event_log(
                    "info",
                    "slot_candidate",
                    "Обнаружен кандидат активного слота",
                    candidate_slot=raw_slot,
                    previous_confirmed_slot=confirmed_slot,
                )

                candidate, values = confirm_active_slot(
                    raw_slot
                )

                if candidate is None:
                    set_state(
                        last_sync_reason=(
                            "slot_confirmation_rejected"
                        ),
                        confirmation_values=values,
                    )

                    event_log(
                        "warning",
                        "slot_confirmation_rejected",
                        "Кандидат активного слота отклонён",
                        candidate_slot=raw_slot,
                        values=values,
                    )

                    time.sleep(POLL_INTERVAL)
                    continue

                previous_slot = confirmed_slot
                confirmed_slot = candidate

                _diagnostics_runtime[
                    "last_slot_confirmed_at"
                ] = timestamp_now()

                set_state(
                    active_slot=confirmed_slot,
                    confirmed_active_slot=confirmed_slot,
                    candidate_slot=confirmed_slot,
                    candidate_reads=(
                        SWITCH_CONFIRMATION_READS
                    ),
                    confirmation_values=values,
                    last_error=None,
                )

                event_log(
                    "info",
                    "slot_confirmed",
                    "Активный слот IFS подтверждён",
                    slot=confirmed_slot,
                    previous_slot=previous_slot,
                    reads=values,
                )

                try:
                    synchronize(
                        force=False,
                        slot=confirmed_slot,
                        reason=(
                            "startup"
                            if previous_slot is None
                            else "confirmed_slot_change"
                        ),
                    )
                except Exception:
                    confirmed_slot = None
                    raise

            else:
                set_state(
                    active_slot=confirmed_slot,
                    confirmed_active_slot=confirmed_slot,
                    candidate_slot=confirmed_slot,
                    candidate_reads=(
                        SWITCH_CONFIRMATION_READS
                    ),
                    confirmation_values=[
                        confirmed_slot
                    ] * SWITCH_CONFIRMATION_READS,
                )

                if state_snapshot().get("last_error"):
                    event_log(
                        "info",
                        "error_recovery_started",
                        "Запущено восстановление синхронизации",
                        slot=confirmed_slot,
                    )

                    try:
                        synchronize(
                            force=False,
                            slot=confirmed_slot,
                            reason="error_recovery",
                        )
                    except Exception:
                        confirmed_slot = None
                        raise

                set_state(last_error=None)

        except Exception as exc:
            set_state(last_error=str(exc))

            event_log(
                "error",
                "monitor_cycle_failed",
                "Ошибка цикла мониторинга",
                error=str(exc),
            )

        time.sleep(POLL_INTERVAL)



class Handler(BaseHTTPRequestHandler):
    # IFS_SPOOLMAN_CORS
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


    server_version="IFS-Spoolman/0.1"
    def log_message(self,fmt,*args): print("%s - %s"%(self.address_string(),fmt%args),flush=True)
    def send_json(self,status,value):
        raw=json.dumps(value,ensure_ascii=False).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def read_json(self):
        length=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(length).decode("utf-8")) if length>0 else {}
    def do_GET(self):
        if self.path=="/api/health":
            self.send_json(200,build_health())
            return
        try:
            if self.path=="/" or self.path.startswith("/index.html"):
                raw=HTML.encode("utf-8"); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw); return
            if self.path=="/api/config":
                self.send_json(200,public_config())
                return
            if self.path=="/api/status":
                with lock: payload=dict(state); payload["assignments"]=dict(assignments)
                self.send_json(200,payload); return
            if self.path=="/api/spools": self.send_json(200,list_spools()); return
            self.send_json(404,{"error":"Not found"})
        except Exception as exc: self.send_json(500,{"error":str(exc)})
    def do_POST(self):
        try:
            if self.path=="/api/assign":
                body=self.read_json(); slot=int(body.get("slot"))
                if slot not in (1,2,3,4): raise ValueError("Некорректный слот")
                value=body.get("spool_id"); spool_id=int(value) if value not in (None,"",0,"0") else None
                with lock:
                    if spool_id is not None:
                        for other_slot,other_id in assignments.items():
                            if other_slot != str(slot) and other_id == spool_id: raise ValueError(f"Катушка ID {spool_id} уже назначена слоту IFS {other_slot}")
                    assignments[str(slot)]=spool_id; atomic_write_json(ASSIGNMENTS_FILE,assignments)
                if state.get("active_slot")==slot: synchronize(True)
                self.send_json(200,{"ok":True}); return
            if self.path=="/api/sync": synchronize(True); self.send_json(200,{"ok":True}); return
            self.send_json(404,{"error":"Not found"})
        except Exception as exc: self.send_json(400,{"error":str(exc)})



def main():
    os.makedirs(APP_DIR, exist_ok=True)
    load_assignments()

    event_log(
        "info",
        "application_started",
        "AD5X IFS Plugin запущен",
        version=APP_VERSION,
        listen_host=LISTEN_HOST,
        listen_port=PORT,
        slot_count=SLOT_COUNT,
        assignments=dict(assignments),
    )

    threading.Thread(
        target=monitor,
        daemon=True,
        name="ad5x-ifs-monitor",
    ).start()

    server = ThreadingHTTPServer(
        (LISTEN_HOST, PORT),
        Handler,
    )

    print(
        f"AD5X IFS Plugin for Spoolman "
        f"{APP_VERSION} listening on "
        f"{LISTEN_HOST}:{PORT}",
        flush=True,
    )

    server.serve_forever()


if __name__=="__main__": main()
