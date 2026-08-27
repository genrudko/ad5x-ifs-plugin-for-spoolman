# Troubleshooting

[Русский](troubleshooting_RU.md)

## Plugin does not run after reboot or power cycle

Start with:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Check `Z-Mod power-on hook`, `Process`, `API health`, and the recent `boot.log` entries.

Autostart must be registered in Z-Mod's supported user startup file:

```text
/usr/data/config/mod_data/power_on.sh
```

It should contain exactly one managed block between:

```text
# >>> AD5X IFS Plugin for Spoolman >>>
# <<< AD5X IFS Plugin for Spoolman <<<
```

If the block is missing, run the release-line installer/update again. Do not replace `power_on.sh` manually.

Inspect startup diagnostics with:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/boot.log
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/ifs_spoolman.log
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/events.log
```

A normal Z-Mod boot may transition from the stock screen to an alternative screen. Serial errors during that handoff are not, by themselves, evidence that this plugin failed.

## The web UI on port 7913 does not open

Check the backend:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
wget -qO- http://127.0.0.1:7913/api/health
```

If the process is absent, run:

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

`start.sh` tolerates normal boot ordering and waits for Moonraker. If Moonraker never starts, repair Z-Mod/Moonraker first.

## Fluidd card is missing or damaged

`status.sh` checks all four current integration parts: `card`, `layout`, `dashboard`, and `selection`.

Starting the backend reapplies current JS assets idempotently and cleans old asset names. Uninstall also removes legacy `visibility`/`controls` injections.

After a Fluidd update, force-refresh the browser (`Ctrl+F5`).

## Spoolman is not connected

Check:

```sh
wget -qO- http://127.0.0.1:7125/server/spoolman/status
```

Expected: `"spoolman_connected": true`.

The plugin does not install or replace Spoolman. Repair the Moonraker-to-Spoolman connection before reinstalling this plugin.

## The active spool does not switch

Run:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Check `active_slot`, `moonraker_spool_id`, slot assignments, `last_error`, and `events.log`.

The backend confirms physical slot changes with multiple reads and retries synchronization. If the active IFS slot has no assigned spool, synchronization is intentionally skipped.

## Multiple backend processes are reported

`status.sh` explicitly reports `multiple backend processes detected`. Safely normalize the service with:

```sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

`stop.sh` validates `/proc/PID/cmdline` and will not terminate an unrelated process merely because an old PID was reused.

## Update failed

The updater creates a timestamped backup under:

```text
/usr/data/config/mod_data/ifs_spoolman/backups/
```

It attempts automatic rollback. Use `status.sh`, `boot.log`, and `ifs_spoolman.log` to verify the restored service.
