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

## 2. Recommended one-command installation and update

Connect to the printer over SSH as `root` and run:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

The `?cb=$(date +%s)` query adds a unique value to the URL so a proxy or CDN cannot return an outdated installer.

This method is designed for a clean Z-Mod installation:

- it does not require `git`;
- it uses the bundled `wget`;
- it avoids `codeload.github.com`, which may fail with TLS alert 80 on the embedded client;
- it downloads only the required files from `raw.githubusercontent.com`;
- it adds cache-busting to every downloaded file;
- it checks Moonraker and Spoolman before changing anything;
- it automatically detects a new or existing installation.

For a new installation, the helper runs `install.sh` and installs the plugin to:

```text
/usr/data/config/mod_data/ifs_spoolman
```

For an existing installation, the helper runs `update.sh`, which:

1. backs up runtime files, `config.json`, and `assignments.json`;
2. stops only the plugin process;
3. copies the new files;
4. starts the plugin;
5. checks `/api/health`;
6. restores the previous version automatically on failure.

Existing configuration and spool assignments are preserved. Klipper, the MCU, Moonraker, Spoolman, and Z-Mod are not removed or reinstalled.

After installation or update, open:

```text
http://PRINTER_IP:7913/
```

Check status:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 3. Why codeload.github.com is not used

On some clean Z-Mod builds, the bundled `wget` can access `raw.githubusercontent.com` but fails while downloading an archive from `codeload.github.com`, reporting TLS alert 80 or `Connection reset by peer`.

The recommended helper therefore does not download or extract a repository archive. It fetches only the files required by the plugin directly from the raw content host.

## 4. Installation with git clone

Use this only when `git --version` works on the printer.

New installation:

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman
git clone https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
cd ad5x-ifs-plugin-for-spoolman
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

Update an existing installation:

```sh
cd /usr/data/ad5x-ifs-plugin-for-spoolman
git pull
./update.sh --dry-run
./update.sh
```

A clean Z-Mod build may not include git. Use the recommended wget command instead of installing extra packages on the printer.

## 5. Runtime commands

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 6. Uninstall

Keep a backup of configuration and logs:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Permanently remove user data:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
