# Architecture

## Components

1. **Python backend** — `plugin/ifs_spoolman.py`
   - reads the AD5X IFS active channel;
   - confirms slot changes;
   - maps slots to Spoolman spool IDs;
   - communicates with Moonraker;
   - serves the web UI and JSON API;
   - records rotating structured events.

2. **Standalone UI** — `plugin/ui_v0_2.html`
   - manages slot assignments;
   - lists Spoolman spools;
   - displays status and allows manual synchronization.

3. **Fluidd card** — `plugin/ifs-spoolman-card.js`
   - periodically reads plugin status;
   - displays the compact AD5X IFS panel.

4. **Fluidd layout helper** — `plugin/ifs-spoolman-layout.js`
   - moves/configures the card inside Fluidd.

5. **Runtime scripts** — `scripts/`
   - start/stop/status;
   - Fluidd install/uninstall;
   - update rollback and data-preserving uninstall.

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
- `assignments.json` — slot-to-spool mapping.
- `events.log*` — structured rotating event logs.
- `ifs_spoolman.log` — process output and HTTP access log.
