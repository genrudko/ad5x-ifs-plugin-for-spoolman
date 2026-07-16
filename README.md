# AD5X IFS Plugin for Spoolman

[Русская документация](README_RU.md)

Community plugin for **Flashforge Adventurer 5X / AD5X with Z-Mod** that synchronizes the active IFS filament slot with the active spool in **Moonraker/Spoolman**.

> **Beta software.** This is an independent community project and is not affiliated with Flashforge, Spoolman, Moonraker, Fluidd, or Z-Mod.

## Spoolman is required before installation

The plugin does **not** install Spoolman and cannot work without it.

Before installing the plugin:

1. install and run Spoolman on a PC, NAS, Raspberry Pi, home server, or VPS;
2. add the Spoolman server URL to `moonraker.conf`;
3. restart Moonraker;
4. verify that Moonraker reports `"spoolman_connected": true`.

See the [mandatory Spoolman setup guide](docs/spoolman.md).

## Features

- Detects the active AD5X IFS slot.
- Maps four IFS slots to Spoolman spool IDs.
- Updates Moonraker's active spool after a confirmed slot change.
- Debounces sensor readings with configurable confirmation reads.
- Avoids redundant spool-switch requests.
- Retries failed synchronization and applies a switch cooldown.
- Provides a standalone web interface on port `7913`.
- Adds an **AD5X IFS** card and layout controls to Fluidd.
- Exposes status, configuration and health API endpoints.
- Writes a rotating structured event log.
- Includes install, update, status and uninstall scripts.

## Requirements

- Flashforge AD5X / Adventurer 5X.
- Clean Z-Mod installation with working Moonraker and Fluidd.
- Spoolman installed and configured beforehand.
- Active Moonraker-to-Spoolman connection.
- Root SSH access to the printer.
- Printer access to `raw.githubusercontent.com`.

## One command for installation and update

Connect over SSH as `root` and run:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

The `?cb=$(date +%s)` parameter prevents an old cached installer from being returned.

The helper:

- verifies Moonraker and Spoolman;
- downloads only the required files directly from `raw.githubusercontent.com`;
- does not require git or `codeload.github.com`;
- adds cache-busting to every downloaded file;
- installs a new copy through `install.sh`;
- updates an existing copy through `update.sh`, including backup, health check, and automatic rollback.

`config.json` and `assignments.json` are preserved during updates. Klipper, the MCU, Moonraker, Spoolman, and Z-Mod are not reinstalled or removed.

Open the management UI at:

```text
http://PRINTER_IP:7913/
```

Detailed instructions: [docs/installation.md](docs/installation.md).

## Status

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## Manual update

From a refreshed checkout:

```sh
./update.sh --dry-run
./update.sh
```

The updater creates a timestamped backup and rolls back automatically if startup or the health check fails.

## Uninstall

Keep user data in a separate backup directory:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Permanently remove plugin data:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```

## Versions

- Package/tooling: `0.6.0-beta`
- Backend: `0.5.0-beta`

## Documentation

- [Mandatory Spoolman setup](docs/spoolman.md)
- [Installation and update](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Fluidd integration](docs/fluidd-integration.md)
- [HTTP API](docs/api.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Security](SECURITY.md)

## License

MIT. See [LICENSE](LICENSE).
