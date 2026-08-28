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
- Debounces sensor readings and retries failed synchronization.
- Avoids redundant spool-switch requests.
- Provides a standalone web interface on port `7913`.
- Adds a native **AD5X IFS Spoolman** Fluidd card with legacy fallback only when needed.
- Exposes status, configuration and health API endpoints plus a rotating structured event log.
- Registers a Z-Mod-native startup hook in user-managed `mod_data/power_on.sh`.
- Uses a persistent Git-managed Z-Mod plugin checkout: after the one-time SSH bootstrap, future updates are delivered through Moonraker/Fluidd Update Manager.
- Applies runtime updates transactionally with backup, health validation, and automatic rollback.

## Requirements

- Flashforge AD5X / Adventurer 5X.
- Z-Mod with working Moonraker and Fluidd. Validated on Z-Mod `1.7.3-1`.
- Spoolman installed and configured beforehand.
- Active Moonraker-to-Spoolman connection.
- Root SSH access for the first installation.
- Printer access to GitHub/raw.githubusercontent.com.

## One SSH command for the first installation

Connect over SSH as `root` and run:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/release/standalone-0.6.x/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

The `?cb=$(date +%s)` parameter prevents an old cached bootstrap script from being returned.

The bootstrap:

- verifies Moonraker and the live Spoolman connection;
- registers `[update_manager ad5x_ifs_spoolman]` in user-managed `mod_data/user.moonraker.conf`;
- creates a persistent Git checkout at `mod_data/plugins/ad5x_ifs_spoolman` through the Z-Mod environment;
- enables the plugin through Z-Mod's supported `plugins.sh` path;
- migrates an older raw-file installation through the safe transactional `update.sh`, preserving `config.json`, `assignments.json`, `power_on.sh`, and the user Moonraker configuration;
- installs/restores the native Fluidd integration.

Persistent Git source:

```text
/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman
```

Runtime:

```text
/usr/data/config/mod_data/ifs_spoolman
```

## Future updates are delivered from Fluidd

After Moonraker has registered the updater, SSH is no longer required for normal updates:

**Fluidd → Software Updates → ad5x_ifs_spoolman → Update**.

Moonraker updates the Git checkout and Z-Mod invokes the repository `update.sh`. Runtime changes are applied transactionally; `config.json` and `assignments.json` are preserved. If startup or the health gate fails, the previously working runtime is restored automatically.

The supported user line is `release/standalone-0.6.x`. Its internal Moonraker channel is intentionally registered as `dev` so Z-Mod follows exactly that branch instead of performing its generic stable-channel reset to an unrelated non-version Git tag.

## Status

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

`status.sh` checks package version, startup hook, backend process, HTTP API, Spoolman synchronization, native Fluidd integration, and absence of a legacy duplicate.

## Web UI

```text
http://PRINTER_IP:7913/
```

## Disable and uninstall

Z-Mod `DISABLE_PLUGIN` invokes the root `uninstall.sh`: the active runtime is removed while the Git checkout and updater registration remain available for a later normal enable.

Manual runtime removal while preserving user data:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Full runtime/data removal:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```

## Versions

- Package/runtime: `0.6.6-beta`
- Validated Z-Mod line: `1.7.3-1`
- Validated native Fluidd integration: `v1.37.4`, patch revision 4

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
