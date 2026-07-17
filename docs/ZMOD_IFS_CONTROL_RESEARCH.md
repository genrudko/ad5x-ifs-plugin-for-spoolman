# Z-Mod IFS control integration research

## Goal

Extend **AD5X IFS Plugin for Spoolman** from passive slot-to-Spoolman synchronization into a safe filament manager for FlashForge AD5X running Z-Mod.

The extension must reuse Z-Mod's existing IFS and filament-change logic rather than reimplementing motor, cutter, purge, sensor, or retry behavior.

## Confirmed Z-Mod capabilities

The current Z-Mod AD5X documentation exposes these relevant commands:

- `IFS_F10` — insert filament;
- `IFS_F11` — remove filament;
- `IFS_F13` — read IFS state;
- `IFS_F15` — reset the IFS driver;
- `IFS_F18` — release filament everywhere;
- `IFS_F23` — mark filament as inserted;
- `IFS_F24` — clamp filament;
- `IFS_F39` — release filament;
- `IFS_F112` — stop filament feeding;
- `PURGE_PRUTOK_IFS` — move filament from IFS towards the extruder;
- `REMOVE_PRUTOK_IFS` — remove a filament by slot number;
- `INSERT_PRUTOK_IFS` — insert a filament by slot number;
- `SET_CURRENT_PRUTOK` — tell Klipper which filament is active;
- `ANALOG_PRUTOK` — load an equivalent filament;
- `IFS_MOTION` — detect stopped or exhausted filament;
- `SET_EXTRUDER_SLOT SLOT=<1..4>` — explicitly declare the slot currently loaded in the extruder.

Z-Mod also documents a native `COLOR` workflow that can:

- display the active extruder slot;
- edit slot colour;
- edit material type;
- load a selected slot;
- unload filament;
- support automatic fallback to another slot with matching material and colour.

## Important operating constraint

Low-level IFS commands and several advanced filament settings require the native printer display to be disabled with `DISPLAY_OFF`. Z-Mod warns that simultaneous access by the native display and the mod can cause serial communication errors.

The plugin therefore must not expose low-level IFS actions blindly. Capability discovery and display-state checks are required before enabling controls.

## Existing plugin foundation

The current plugin already provides:

- a local HTTP backend on port `7913`;
- Moonraker connectivity;
- active-slot monitoring from `Adventurer5M.json` / `FFMInfo.channel`;
- stable slot confirmation;
- slot-to-Spoolman assignments;
- automatic Moonraker active-spool synchronization;
- a Fluidd dashboard card;
- event logging and diagnostics.

This makes the project an extension of the current architecture, not a separate plugin.

## Proposed architecture

### 1. Capability discovery

Add a read-only backend capability probe that queries Moonraker for registered G-code macros and printer state.

Expected result shape:

```json
{
  "zmod_detected": true,
  "ifs_control_available": true,
  "display_off_required": true,
  "macros": {
    "insert": "INSERT_PRUTOK_IFS",
    "remove": "REMOVE_PRUTOK_IFS",
    "set_extruder_slot": "SET_EXTRUDER_SLOT",
    "stop": "IFS_F112",
    "state": "IFS_F13"
  }
}
```

No write operation should be enabled unless the required macros are confirmed on the installed printer.

### 2. Operation state machine

Introduce a backend-owned operation record:

```text
idle
  -> validating
  -> heating
  -> unloading
  -> switching_path
  -> loading
  -> purging
  -> synchronizing_spoolman
  -> completed
```

Error and cancellation states:

```text
failed
cancel_requested
cancelled
```

Only one filament operation may run at a time.

### 3. Safe command layer

Expose high-level API actions rather than arbitrary G-code:

- `POST /api/filament/load`
- `POST /api/filament/unload`
- `POST /api/filament/change`
- `POST /api/filament/stop`
- `GET /api/filament/status`
- `GET /api/filament/capabilities`

The backend must validate:

- slot range;
- assigned Spoolman spool;
- printer state;
- extruder temperature requirements;
- presence of required macros;
- no conflicting operation;
- display / IFS access mode where detectable.

### 4. Spoolman synchronization

After a successful physical load or change:

1. confirm the physical active slot;
2. run or verify `SET_EXTRUDER_SLOT` / `SET_CURRENT_PRUTOK` as required by Z-Mod;
3. update Moonraker's active Spoolman spool;
4. confirm the resulting spool ID;
5. write an event-log entry.

Spoolman must never be switched merely because the user opened another slot for inspection.

### 5. Fluidd UI model

Keep two distinct visual states:

- **active slot** — physical filament currently selected by IFS;
- **inspected slot** — slot whose details are open in the card.

Planned controls:

- Load selected slot;
- Unload active filament;
- Change active filament to selected slot;
- Stop current IFS operation;
- Open advanced manager.

During an operation the card should show the current phase and disable conflicting controls.

## Delivery phases

### Phase A — read-only discovery

- detect Z-Mod and required macros;
- expose capabilities endpoint;
- expose printer / IFS control readiness in diagnostics;
- no physical movement commands.

### Phase B — explicit manual actions

- unload active filament;
- load selected slot;
- stop operation;
- operation lock, status and logs;
- no automatic chaining beyond documented Z-Mod commands.

### Phase C — full change workflow

- unload current slot;
- load target slot;
- confirm physical state;
- synchronize Moonraker and Spoolman;
- recover safely from partial failures.

### Phase D — richer integration

- colour and material metadata bridge;
- equivalent-spool fallback;
- optional automatic slot replacement;
- print-time restrictions and confirmation dialogs.

## Research still required before write actions

The public documentation confirms command names and purpose but does not fully define every command parameter, response, asynchronous completion signal, or safe printer-state restriction.

Before Phase B, inspect the actual Z-Mod implementation and/or query the installed Moonraker object list for:

- exact parameter names for `INSERT_PRUTOK_IFS` and `REMOVE_PRUTOK_IFS`;
- whether the commands block until completion;
- how errors are surfaced;
- how operation completion can be observed;
- which macro represents the native high-level `COLOR` load/unload action;
- native-display state and `DISPLAY_OFF` detection;
- restrictions during printing, pause, cancellation, and shutdown.

## Safety boundary

Initial implementation must remain read-only until capability discovery is reliable. Physical IFS movement will only be added through explicit, validated high-level actions with serialized execution and auditable logs.
