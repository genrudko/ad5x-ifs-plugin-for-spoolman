# Changelog

## 0.6.4-beta — 2026-08-27

### Fixed

- Added standalone startup through Z-Mod's supported `mod_data/power_on.sh`; existing user code is preserved and repeated installs remain idempotent.
- Removed the boot race where the wrapper could fail before the Moonraker process appeared.
- PID files are no longer trusted blindly: process command lines are validated, orphaned running backends can be adopted, and duplicate launches are prevented.
- `stop.sh` no longer risks terminating an unrelated process after PID reuse.
- `status.sh` now checks the startup hook, PID ownership, duplicate backends, API health, every Fluidd component, and recent boot/event logs.
- Uninstall now removes dashboard and legacy Fluidd injections and removes only the plugin-owned block from `power_on.sh`.
- Fluidd `index.html` changes are now written atomically during install and uninstall.
- The installer is pinned to the standalone maintenance line `release/standalone-0.6.x` instead of experimental `main` development.
- Fixed first startup without `config.json`: the atomic JSON helper is defined before configuration loading.
- Added an explicit `urllib.parse` import instead of depending on incidental package import behavior.
- Removed stale `0.2.2`/`0.1` version strings from the embedded UI and HTTP server metadata.
- Synchronized the package manifest, documentation, and flattened installer file set.

### Versions

- Package/tooling: `0.6.4-beta`.
- Backend: `0.5.1-beta`.

## 0.6.0-beta — 2026-07-17

### Added

- Install, update, status and uninstall tooling.
- Data-preserving update and uninstall behavior.
- Automatic update rollback after failed start or health check.
- Fluidd asset cleanup and uninstall support.
- Repository packaging and example configuration files.

### Backend 0.5.0-beta

- `/api/health` endpoint.
- Structured rotating event log.
- Uptime and component-level diagnostics.
- Synchronization counters and timestamps.

### Backend 0.4.0-beta

- Confirmed multi-read slot switching.
- Retry handling and switch cooldown.
- Redundant switch suppression.
