# Installation and update

## Before installation

Confirm that Z-Mod, Moonraker and Fluidd are already working and that Moonraker can reach Spoolman. The installer does not install or configure Spoolman itself.

## Install from a repository checkout

1. Transfer the repository directory to the printer.
2. Connect over SSH as `root`.
3. Enter the repository directory.
4. Run:

```sh
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

Use `./install.sh --no-start` to copy files without starting the service.

The installer creates missing `config.json` and `assignments.json` from the examples. Existing user files are not overwritten.

## Update

```sh
./update.sh --dry-run
./update.sh
```

The update process:

1. validates the source tree;
2. backs up runtime files and user configuration;
3. stops only the plugin process;
4. copies the new runtime files;
5. starts the plugin;
6. checks `/api/health`;
7. rolls back automatically on failure.

Klipper, Moonraker and the printer MCU are not restarted by these scripts.

## Runtime commands

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## Uninstall

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

This removes the service and Fluidd integration and copies user configuration/logs to a timestamped directory under `/usr/data/config/mod_data/`.

Use `--purge` only when the user data must also be deleted.
