# Changelog

## 0.6.6-beta — 2026-08-28
### Hotfix — 2026-08-29

- Native Fluidd dashboard slots now show spool name, vendor, Spoolman ID, material and compact remaining weight/percentage directly in each IFS lane; the redundant selected-spool detail block was removed. Native UI compatibility revision is now v5 and updates are applied automatically when the installed revision is older.
- Added IFS↔Spoolman assignment interoperability through Moonraker `lane_data`: HelixScreen assignments are imported automatically, while plugin edits update only the lane `spool_id` without clobbering Helix material/color/vendor metadata. A durable sync snapshot resolves later two-way edits without wiping legacy local assignments on first bridge startup.
- Added automatic recovery of previous IFS↔Spoolman assignments from pre-git/update backups during migration when the current `assignments.json` is empty; non-empty current assignments are never overwritten.
- Fixed stale UI/server version identity by deriving runtime surfaces from the installed package version.
- Spoolman connectivity is now probed independently of IFS slot assignment, so a fresh `0/4` assignment state no longer reports a false offline status.
- Synchronization and health monitoring share one Moonraker Spoolman status parser; health polling remains low-load and assignment-independent.


### Added

- Migrated the plugin to Z-Mod's native Git-managed model with a persistent checkout in `mod_data/plugins/ad5x_ifs_spoolman`.
- After the one-time SSH bootstrap, future updates are delivered through Moonraker/Fluidd Update Manager without rerunning the installer.
- Added `ad5x_ifs_spoolman.cfg`, a root `uninstall.sh`, and owned registration of `[update_manager ad5x_ifs_spoolman]`.
- Existing raw-file installs migrate through the transactional `update.sh` while preserving `config.json`, `assignments.json`, `power_on.sh`, and `user.moonraker.conf`.
- Updating the source checkout while the runtime is disabled no longer re-enables it implicitly.

### Fixed

- Backend runtime version is now stamped from package `VERSION`, so API and package reporting stay consistent.
- `status.sh` correctly detects the native Fluidd integration and separately checks for unexpected legacy injection.
- The update health gate no longer depends on the embedded `wget`; it uses Moonraker's Python plus `urllib.request` and validates the JSON `application` field.
- The production line follows `release/standalone-0.6.x` with Moonraker `channel: dev`. This is intentional because Z-Mod's `stable` plugin path performs a generic reset to the globally latest Git tag, while this repository also contains a separate Fluidd compatibility tag.

### Real AD5X validation

- The full Git update path was validated on real hardware before and after migration to Z-Mod `1.7.3-1`.
- Verified `git fetch/pull -> update.sh -> runtime apply -> health gate`, preserved spool assignments, and working Spoolman synchronization.
- After a real cold boot on Z-Mod `1.7.3-1`, the plugin started automatically, Moonraker re-registered the updater, Fluidd discovered the next update, and the update completed successfully.

## 0.6.5-beta — 2026-08-28

### Added

- Native Vue/Vuetify Fluidd card replacing the primary legacy DOM injection.
- Automatic compatibility path for the official `ghzserg/fluidd` release line; the current validated build targets Fluidd `v1.37.4`, patch revision 4.
- Legacy injection remains only as a fallback and is cleaned automatically when native integration succeeds.

### Real AD5X validation

- After a printer reboot the backend started automatically and Fluidd displayed exactly one native `AD5X IFS Spoolman` card.

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
