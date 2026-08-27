# Architecture

[Русский](architecture_RU.md)

## Components

1. **Python backend** — `plugin/ifs_spoolman.py`
   - reads the AD5X IFS active channel;
   - confirms slot changes;
   - maps the four physical slots to Spoolman spool IDs;
   - communicates with Moonraker;
   - serves the web UI and JSON API;
   - records rotating structured events.

2. **Standalone UI** — `plugin/ui_v0_2.html`
   - manages slot assignments;
   - lists Spoolman spools;
   - displays status and allows manual synchronization.

3. **Fluidd integration**
   - `plugin/ifs-spoolman-card.js` — card;
   - `plugin/ifs-spoolman-layout.js` — placement;
   - `plugin/ifs-spoolman-dashboard.js` — Dashboard-only/collapse behavior;
   - `plugin/ifs-spoolman-selection.js` — active/viewed slot indication.

4. **Z-Mod lifecycle**
   - `scripts/power_on_hook.sh` idempotently manages only its marked block in `mod_data/power_on.sh`;
   - the block tolerates both visible Z-Mod runtime namespaces, `/usr/data/config/...` and `/opt/config/...`;
   - `scripts/start.sh` waits for Moonraker and enters its chroot;
   - `scripts/boot_start.sh` applies/removes Fluidd integration according to `fluidd_integration`, normalizes PID state, and starts the backend;
   - `scripts/stop.sh` terminates only processes whose command line actually belongs to `ifs_spoolman.py`.

5. **Installation and maintenance**
   - installation/update is pinned to `release/standalone-0.6.x`;
   - update uses backup, health check, and rollback;
   - uninstall preserves user data by default, cleans Fluidd, and removes only the plugin-owned startup block.

## Synchronization flow

1. Poll the AD5X IFS channel.
2. Require a configured number of matching confirmation reads.
3. Resolve the confirmed slot to a Spoolman spool ID.
4. Query Moonraker's current active spool.
5. Skip the request when the desired spool is already active.
6. Otherwise apply cooldown, switch the spool and verify the returned ID.
7. Retry transient failures and record the result.

## Persistent data

- `config.json` — runtime settings.
- `assignments.json` — four-slot-to-spool mapping.
- `events.log*` — structured rotating event logs.
- `ifs_spoolman.log` — process output and HTTP access log.
- `boot.log` — startup hook/wrapper output.
- `backups/` — update backups.

## Product boundary

This architecture belongs only to the original standalone **AD5X IFS Plugin for Spoolman**. The later Filament Manager experiments and frontend-neutral IFS / Materials Manager work in `Plugins_AD5X` are not runtime components of this maintenance line.
