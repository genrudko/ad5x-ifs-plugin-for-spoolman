# Troubleshooting

## Check the complete state

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## The web UI does not open

Check that the process is running and port `7913` is reachable. Inspect:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/ifs_spoolman.log
```

## Health is `degraded` or `error`

Open:

```text
http://PRINTER_IP:7913/api/health
```

Review the individual `ifs_sensor`, `moonraker` and `spoolman` components, then inspect:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/events.log
```

## Fluidd card is missing

Reapply the static integration:

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

Or run the inner installer from the Moonraker chroot using the existing `start.sh` flow. Refresh Fluidd without browser cache afterward.

## Wrong spool becomes active

Check `assignments.json` or correct assignments in the web UI. Confirm that the IFS slot shown by `/api/status` matches the physical active channel.

## Update failed

The updater creates a timestamped backup under:

```text
/usr/data/config/mod_data/ifs_spoolman/backups/
```

It attempts automatic rollback. Use `status.sh` and logs to verify the restored service.
