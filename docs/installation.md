# Installation and update on a clean Z-Mod system

[Русский](installation_RU.md)

## 1. Install and configure Spoolman first

This is mandatory. The plugin does not install Spoolman and cannot work until Moonraker is actively connected to it.

Complete the [Spoolman setup guide](spoolman.md), then verify on the printer:

```sh
wget -qO- http://127.0.0.1:7125/server/spoolman/status
```

The response must contain:

```json
"spoolman_connected": true
```

## 2. Recommended one-command installation

Connect to the printer over SSH as `root` and run:

```sh
wget -qO /tmp/ad5x-ifs-install.sh https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

This method is designed for a clean Z-Mod installation. It does not require `git`, avoids unsupported BusyBox `tar -z` usage, verifies Moonraker and Spoolman, downloads the repository, extracts it, and runs the installer.

## 3. Manual download without git

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman-main ad5x-ifs-plugin-main.tar.gz
wget -O ad5x-ifs-plugin-main.tar.gz https://codeload.github.com/genrudko/ad5x-ifs-plugin-for-spoolman/tar.gz/refs/heads/main
mkdir -p ad5x-ifs-download
gzip -dc ad5x-ifs-plugin-main.tar.gz | tar -C ad5x-ifs-download -xf -
cd ad5x-ifs-download/ad5x-ifs-plugin-for-spoolman-main
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

## 4. Installation with git clone

Use this only when `git --version` works on the printer:

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman
git clone https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
cd ad5x-ifs-plugin-for-spoolman
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

A clean Z-Mod build may not include git. Use the recommended wget method instead of trying to install additional packages on the printer.

## 5. Update

From a refreshed checkout or newly extracted repository:

```sh
./update.sh --dry-run
./update.sh
```

The updater validates the source tree, creates a backup, stops only the plugin, copies the new runtime files, starts the plugin, checks `/api/health`, and rolls back automatically on failure.

Klipper, Moonraker and the printer MCU are not restarted by these scripts.

## Runtime commands

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## Uninstall

Keep a backup of configuration and logs:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Permanently remove user data:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
