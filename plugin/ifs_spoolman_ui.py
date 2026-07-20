#!/usr/bin/env python3
"""Phase B3: standalone web UI for native Z-Mod slot metadata."""

import os
import urllib.parse

import ifs_spoolman as core
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.7.4-beta"
MANAGER_HTML = os.path.join(core.APP_DIR, "zmod-filaments.html")
_BaseHandler = writer.WriteRuntimeHandler
_original_public_config = writer.public_config
_original_build_health = writer.build_health


def public_config():
    payload = _original_public_config()
    payload["application_version"] = RUNTIME_VERSION
    payload["zmod_metadata"]["manager_url"] = "/manager"
    return payload


def build_health():
    health = _original_build_health()
    health["version"] = RUNTIME_VERSION
    health.setdefault("components", {}).setdefault("zmod_metadata", {})[
        "manager_url"
    ] = "/manager"
    return health


class UiRuntimeHandler(_BaseHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in {"/manager", "/manager/", "/zmod-filaments.html"}:
            try:
                with open(MANAGER_HTML, "rb") as stream:
                    raw = stream.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(raw)
            except FileNotFoundError:
                self.send_json(404, {"error": "Страница менеджера не установлена"})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
            return
        super().do_GET()


writer.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.public_config = public_config
core.build_health = build_health
core.Handler = UiRuntimeHandler


if __name__ == "__main__":
    core.main()
