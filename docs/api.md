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

Returns overall health, uptime and separate IFS sensor, Moonraker and Spoolman component states.

Overall status values:

- `ok`
- `degraded`
- `error`

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
