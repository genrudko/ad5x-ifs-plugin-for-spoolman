# Configuration

[Русский](configuration_RU.md)

Runtime configuration is stored at:

```text
/usr/data/config/mod_data/ifs_spoolman/config.json
```

Slot assignments are stored separately in `assignments.json` and are normally edited through the web UI.

## Parameters

| Key | Default | Purpose |
|---|---:|---|
| `schema_version` | `1` | Configuration schema version. |
| `moonraker_url` | `http://127.0.0.1:7125` | Local Moonraker API base URL. |
| `listen_host` | `0.0.0.0` | Plugin HTTP bind address. |
| `listen_port` | `7913` | Plugin HTTP port. |
| `slot_count` | `4` | Fixed number of physical AD5X IFS slots. Only `4` is supported. |
| `poll_interval` | `1.0` | Sensor polling interval in seconds. |
| `http_timeout` | `5.0` | Moonraker request timeout. |
| `spoolman_proxy_timeout` | `10.0` | Spoolman proxy request timeout. |
| `switch_confirmation_reads` | `3` | Matching sensor reads required before accepting a slot. |
| `switch_confirmation_interval` | `0.25` | Delay between confirmation reads. |
| `switch_cooldown` | `2.0` | Minimum delay between actual spool switches. |
| `sync_retry_count` | `3` | Number of synchronization attempts. |
| `sync_retry_delay` | `1.0` | Delay between attempts. |
| `event_log_max_bytes` | `524288` | Maximum structured event-log size before rotation. |
| `event_log_backup_count` | `3` | Number of rotated event logs to retain. |
| `fluidd_integration` | `true` | Enables the static Fluidd card/integration. When set to `false`, an existing injected integration is removed on the next plugin start. |

Unknown keys and invalid value types are rejected. `slot_count` is intentionally not a generic MMU adaptation control: this standalone release targets the four-slot AD5X IFS hardware.

After manually editing the file, restart only the plugin:

```sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```
