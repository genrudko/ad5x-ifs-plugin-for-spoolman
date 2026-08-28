# Installation and update on Z-Mod

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

## 2. First installation: one SSH command

Connect to the printer as `root` and run:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/release/standalone-0.6.x/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

`release/standalone-0.6.x` is the maintained standalone line. The `?cb=$(date +%s)` parameter prevents an outdated cached bootstrap script from being returned.

The bootstrap only performs the initial Z-Mod integration:

1. checks Moonraker and Spoolman;
2. registers the owned `[update_manager ad5x_ifs_spoolman]` block in `/usr/data/config/mod_data/user.moonraker.conf`;
3. creates a Git checkout at `/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman` using Git inside the Z-Mod environment;
4. enables the plugin through Z-Mod's supported `plugins.sh` path;
5. migrates an older raw-file runtime through the transactional `update.sh`;
6. preserves user `config.json`, `assignments.json`, `power_on.sh`, and Moonraker configuration;
7. installs/restores the native Fluidd integration.

Runtime remains separate:

```text
/usr/data/config/mod_data/ifs_spoolman
```

Git source:

```text
/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman
```

## 3. All future updates are delivered through Fluidd

After updater registration, the SSH bootstrap does not need to be rerun.

Open:

**Fluidd → Software Updates → ad5x_ifs_spoolman**

and press **Update**.

Moonraker updates the Git source checkout, then Z-Mod invokes the repository root `update.sh`. The updater:

1. snapshots managed runtime and external files modified by the plugin;
2. stops only the plugin backend;
3. applies the new runtime;
4. restores/updates the boot hook;
5. starts the backend;
6. validates `/api/health` with Moonraker's Python and checks the JSON `application` field;
7. restores the previously working runtime automatically if acceptance fails.

Existing configuration and spool assignments are preserved.

## 4. Why update_manager uses `channel: dev`

This does **not** mean users receive an experimental branch. The user-facing line is pinned to `release/standalone-0.6.x`.

The reason is technical: for plugin updaters using `channel: stable`, Z-Mod runs a generic `reset_git.sh` that resets the checkout to the globally latest Git tag. This repository also carries a separate non-version `fluidd-compatibility` tag, so that reset can select something other than a standalone release.

The production bootstrap therefore registers:

```ini
[update_manager ad5x_ifs_spoolman]
type: git_repo
channel: dev
path: /root/printer_data/config/mod_data/plugins/ad5x_ifs_spoolman
origin: https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
is_system_service: False
primary_branch: release/standalone-0.6.x
```

Release stability is controlled by the release branch; `channel: dev` is used only as Moonraker's branch-tracking mode.

## 5. Startup

The plugin adds only its own marked block to:

```text
/usr/data/config/mod_data/power_on.sh
```

Unrelated user code is preserved. After a cold boot the backend starts automatically and can recover Moonraker/Spoolman connectivity if those services become available slightly later.

## 6. Status check

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Expected results include:

- `Package version: 0.6.6-beta`;
- `Status: RUNNING`;
- API `status: ok`;
- Spoolman connected;
- `Native Fluidd: installed` when a compatible native build is available;
- `Legacy Fluidd injection: clean` with native integration.

## 7. Validated compatibility

Release `0.6.6-beta` was validated on real AD5X hardware with Z-Mod `1.7.3-1`:

- the Z-Mod migration preserved runtime/config/assignments;
- a Git update through Moonraker invoked repository `update.sh` successfully;
- the runtime health gate passed;
- after a real cold boot the updater reappeared in Fluidd;
- the next update was discovered and installed from Fluidd.

## 8. Disable and uninstall

Z-Mod `DISABLE_PLUGIN` removes the include and invokes the repository root `uninstall.sh`. Z-Mod's `plugins.sh` does not delete the Git checkout, so source/update-manager state remains available for a later enable.

Manual runtime removal while preserving user data:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Full runtime/data removal:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
