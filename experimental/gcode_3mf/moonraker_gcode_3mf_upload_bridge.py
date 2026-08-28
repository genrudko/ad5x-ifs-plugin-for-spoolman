#!/usr/bin/env python3
"""Experimental Moonraker upload bridge for sliced .gcode.3mf.

Moonraker's OctoPrint-compatible upload endpoint accepts arbitrary files, but
only files whose final extension is present in file_manager.VALID_GCODE_EXTS
enter the G-code upload path. OrcaSlicer sends `print=true` in the same
/api/files/local upload request; for an unrecognised .3mf extension Moonraker
therefore stores the file as a generic file and never calls
klippy_apis.start_print().

This component makes the smallest possible runtime-only change: it adds .3mf
to Moonraker's in-memory VALID_GCODE_EXTS list. It does not modify Moonraker
source files on disk. The existing experimental [gcode_3mf] component remains
responsible for validating/extracting the sliced container and intercepting the
actual start request.

Removing this component and restarting Moonraker restores the original
extension list automatically.
"""

from __future__ import annotations

import logging

from moonraker.components.file_manager import file_manager


class GCode3MFUploadBridge:
    def __init__(self, config):
        self.server = config.get_server()
        ext = ".3mf"
        if ext not in file_manager.VALID_GCODE_EXTS:
            file_manager.VALID_GCODE_EXTS.append(ext)
        logging.info(
            "GCode3MF upload bridge enabled; VALID_GCODE_EXTS=%s",
            file_manager.VALID_GCODE_EXTS,
        )


def load_component(config):
    return GCode3MFUploadBridge(config)
