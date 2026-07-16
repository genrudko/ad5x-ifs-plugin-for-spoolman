# Mandatory Spoolman setup

[Русский](spoolman_RU.md)

## Important

**AD5X IFS Plugin for Spoolman does not replace or install Spoolman.**

Before installing the plugin, all of the following must already be true:

1. Spoolman is installed and running on another computer or server;
2. the printer can reach that server over the network;
3. Moonraker is configured to use Spoolman;
4. Moonraker reports `spoolman_connected: true`.

Spoolman may run on a NAS, always-on PC, Raspberry Pi, home server, or VPS reachable by the printer.

## 1. Determine the Spoolman URL

A typical address is:

```text
http://SPOOLMAN_SERVER_IP:7912
```

Open that address in a browser and confirm that the Spoolman interface loads.

## 2. Configure Moonraker

Add or update this section in `moonraker.conf`:

```ini
[spoolman]
server: http://SPOOLMAN_SERVER_IP:7912
```

Do not create a duplicate `[spoolman]` section.

## 3. Restart Moonraker

After editing `moonraker.conf`, restart Moonraker through Z-Mod or Fluidd.

## 4. Verify over SSH

Run on the printer as `root`:

```sh
wget -qO- http://127.0.0.1:7125/server/spoolman/status
```

A working connection must contain:

```json
"spoolman_connected": true
```

The AD5X IFS installer stops without modifying the plugin installation when Moonraker is not actively connected to Spoolman.

Common causes include an incorrect URL or port, firewall rules, unreachable networks, an offline Spoolman server, duplicate Moonraker sections, or failing to restart Moonraker after editing its configuration.

After the status reports `true`, continue with [plugin installation](installation.md).
