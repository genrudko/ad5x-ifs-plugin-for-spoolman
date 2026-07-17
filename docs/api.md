# HTTP API

Default base URL:

```text
http://PRINTER_IP:7913
```

The current beta API is intended for a trusted local network and does not provide authentication.

## `GET /`

Standalone management interface.

## `GET /api/status`

Returns the active/raw/confirmed slot, Moonraker spool ID, connectivity, synchronization state, counters and slot assignments.

## `GET /api/health`

Returns overall health, uptime and separate IFS sensor, Moonraker, Spoolman and read-only filament-control discovery states.

Overall status values:

- `ok`
- `degraded`
- `error`

## `GET /api/filament/capabilities`

Performs read-only discovery of the Z-Mod IFS control surface through Moonraker. The endpoint does not execute G-code and cannot move filament.

The response includes:

- whether Moonraker was reachable;
- whether Z-Mod markers were detected;
- registered high-level and low-level IFS macros;
- missing required macro roles;
- current Klipper and print state;
- extruder temperature and target;
- native-display readiness status;
- explicit `read_only` and `write_actions_enabled` flags.

Capability results are cached for five seconds. Append `?refresh=1` to force a new probe:

```text
GET /api/filament/capabilities?refresh=1
```

During Phase A, `write_actions_enabled` and `control_ready` always remain `false`. The native display state is reported as `unknown` unless a reliable read-only signal is added later.

## `GET /api/config`

Returns the effective public configuration and application version.

## `GET /api/spools`

Returns the Spoolman spool list through the Moonraker/Spoolman integration.

## `POST /api/assign`

Assigns a Spoolman spool ID to an IFS slot. The web UI uses this endpoint.

## `POST /api/sync`

Forces a synchronization attempt for the currently detected slot.

## Compatibility

The API is beta and may change before version 1.0. Consumers should tolerate additional JSON fields.
