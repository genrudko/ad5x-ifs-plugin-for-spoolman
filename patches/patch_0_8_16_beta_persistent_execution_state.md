# Patch 0.8.16-beta — persistent IFS execution state repair

## Target
Fix the prepare → execute lifecycle introduced in 0.8.15-beta.

## Confirmed defect
`prepare_operation()` stores one-time tokens only in process memory (`_pending_tokens`). `execute_operation()` depends on the same runtime dictionary, which makes the prepared operation fragile and causes opaque HTTP 409 responses.

## Changes

### plugin/ifs_spoolman_planner.py

1. Add persistent pending-operation storage.

Store:
- operation_id
- token
- created_at
- expires_at
- request
- gcode_preview
- active_slot
- target_presence
- plan hash

2. Replace RAM-only token lifecycle:

Before:
```
_pending_tokens[token] = entry
```

After:
```
save_pending_operation(entry)
```

3. Execute flow:

```
load pending state
validate token
validate TTL
validate confirmation phrase
recalculate plan
compare state snapshot
queue worker
remove pending state
```

4. Add structured errors:

- token_not_found
- token_expired
- token_mismatch
- operation_in_progress
- plan_changed
- target_state_changed

5. Keep asynchronous worker unchanged:

```
queued
submitting
running
completed/failed
```

6. Add automatic cleanup:

- completed
- failed
- expired
- rejected

## Additional repair

Synchronize contract state so readiness and contract endpoints use the same validated contract cache.

## Verification scenario

```
prepare slot=4
execute token
GET operation
wait completed
GET readiness
verify active_slot=4
```
