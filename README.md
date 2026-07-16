# AD5X IFS Plugin for Spoolman

[Русская документация](README_RU.md)

Community plugin for **Flashforge Adventurer 5X / AD5X with Z-Mod** that synchronizes the active IFS filament slot with the active spool in **Moonraker/Spoolman**.

> **Beta software.** This is an independent community project and is not affiliated with Flashforge, Spoolman, Moonraker, Fluidd, or Z-Mod.

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
- Z-Mod with Moonraker and Fluidd.
- Moonraker connected to a working Spoolman server.
- Root SSH access to the printer.

## Installation

Copy or clone this repository to the printer, enter the repository directory, then run:

```sh
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

The runtime files are installed to:

```text
/usr/data/config/mod_data/ifs_spoolman
```

Open the management UI at:

```text
http://PRINTER_IP:7913/
```

Detailed instructions: [docs/installation.md](docs/installation.md).

## Update

From a newer checkout or extracted release:

```sh
./update.sh --dry-run
./update.sh
```

`config.json` and `assignments.json` are preserved. The updater creates a timestamped backup and performs rollback if the service or health endpoint fails.

## Status

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

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

- [Installation and update](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Fluidd integration](docs/fluidd-integration.md)
- [HTTP API](docs/api.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Security](SECURITY.md)

## License

MIT. See [LICENSE](LICENSE).
