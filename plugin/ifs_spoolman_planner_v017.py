#!/usr/bin/env python3
"""Live-telemetry execution layer for AD5X IFS control.

This runtime extends the guarded 0.8.16-beta prepare/execute contract. The
Moonraker G-code request is performed in its own submitter thread while the
operation worker independently polls printer state, so the status endpoint can
report heating, filament motion and completion instead of remaining stuck in
"submitting" until the macro returns.
"""

import socket
import threading
import time
import urllib.error

import ifs_spoolman as core
import ifs_spoolman_control as control
import ifs_spoolman_local as local
import ifs_spoolman_planner as planner
import ifs_spoolman_planner_v016 as persistent
import ifs_spoolman_runtime as runtime
import ifs_spoolman_ui as ui
import ifs_spoolman_writer as writer


RUNTIME_VERSION = "0.8.18-beta-repair1"
_BaseHandler = persistent.PersistentPlannerRuntimeHandler


def _float_or_zero(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _submission_timeout(exc):
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, urllib.error.URLError):
        return isinstance(getattr(exc, "reason", None), socket.timeout)
    return False


def _progress_phase(plan, observed, request_done, activity_seen):
    target = _float_or_zero(observed.get("extruder_target"))
    temperature = _float_or_zero(observed.get("extruder_temperature"))
    active_slot = observed.get("active_slot")

    if target > 0.5:
        if temperature + 5.0 < target:
            return "heating"
        return "filament_change"

    if plan.get("action") in {"load", "switch"}:
        if active_slot == plan.get("target_slot"):
            return "finalizing"
        return "waiting_for_slot_change" if activity_seen else "waiting_for_macro_activity"

    if request_done and activity_seen:
        return "finalizing"
    return "filament_change" if activity_seen else "waiting_for_macro_activity"


def _submitter(script, result, done_event):
    try:
        result["response"] = planner._submit_gcode(script)
    except Exception as exc:  # The worker classifies the exception safely.
        result["exception"] = exc
    finally:
        done_event.set()


def _mark_failed(operation_id, code, message, observed=None):
    planner._set_operation(
        status="failed",
        failed=True,
        completed=False,
        completed_at=core.timestamp_now(),
        progress_phase="failed",
        error={"code": code, "message": message},
        observed=observed or {},
        moonraker_request_in_flight=False,
    )
    core.event_log(
        "error",
        "ifs_operation_failed_live_telemetry",
        "Операция IFS завершилась ошибкой",
        operation_id=operation_id,
        error_code=code,
        error=message,
    )


def live_operation_worker(operation_id, plan):
    """Submit G-code and monitor physical state concurrently."""

    with planner._execution_lock:
        started_at = core.timestamp_now()
        planner._set_operation(
            status="submitting",
            started_at=started_at,
            submission_started_at=started_at,
            submitted_at=None,
            gcode_submitted=False,
            telemetry_enabled=True,
            telemetry_interval_seconds=planner.MONITOR_INTERVAL_SECONDS,
            progress_phase="dispatching",
            activity_seen=False,
            moonraker_request_in_flight=False,
            moonraker_acknowledged=False,
            moonraker_acknowledged_at=None,
            submission_uncertain=False,
            submission_error=None,
        )

        submit_result = {}
        submit_done = threading.Event()
        submit_thread = threading.Thread(
            target=_submitter,
            args=(plan["gcode_preview"], submit_result, submit_done),
            name=f"ifs-submit-{operation_id}",
            daemon=True,
        )
        try:
            submit_thread.start()
        except Exception as exc:
            _mark_failed(
                operation_id,
                "submitter_start_failed",
                f"Не удалось запустить поток отправки команды: {exc}",
            )
            return

        submitted_at = core.timestamp_now()
        planner._set_operation(
            status="running",
            gcode_submitted=True,
            submitted_at=submitted_at,
            moonraker_request_in_flight=True,
            progress_phase="waiting_for_macro_activity",
        )
        core.event_log(
            "warning",
            "ifs_operation_dispatch_started",
            "Команда IFS передана в отдельный поток отправки",
            operation_id=operation_id,
            action=plan.get("action"),
            target_slot=plan.get("target_slot"),
            gcode=plan.get("gcode_preview"),
        )

        deadline = time.monotonic() + planner.MONITOR_TIMEOUT_SECONDS
        activity_seen = False
        submission_handled = False
        submission_acceptable = False
        last_observed = {}

        while time.monotonic() < deadline:
            if submit_done.is_set() and not submission_handled:
                submission_handled = True
                exc = submit_result.get("exception")
                if exc is None:
                    submission_acceptable = True
                    planner._set_operation(
                        moonraker_request_in_flight=False,
                        moonraker_acknowledged=True,
                        moonraker_acknowledged_at=core.timestamp_now(),
                        moonraker=submit_result.get("response"),
                        submission_error=None,
                    )
                elif _submission_timeout(exc):
                    # Moonraker can continue a long macro after the HTTP client
                    # stops waiting. Physical-state monitoring remains decisive.
                    submission_acceptable = True
                    planner._set_operation(
                        moonraker_request_in_flight=False,
                        moonraker_acknowledged=False,
                        submission_uncertain=True,
                        submission_error=str(exc),
                    )
                else:
                    _mark_failed(
                        operation_id,
                        "moonraker_submission_failed",
                        str(exc),
                        observed=last_observed,
                    )
                    return

            try:
                observed = planner._observed_state()
                last_observed = observed
                target = _float_or_zero(observed.get("extruder_target"))
                active_changed = (
                    observed.get("active_slot") != plan.get("active_slot")
                )
                if target > 0.5 or active_changed:
                    activity_seen = True

                phase = _progress_phase(
                    plan,
                    observed,
                    request_done=submit_done.is_set(),
                    activity_seen=activity_seen,
                )
                planner._set_operation(
                    status="running",
                    observed=observed,
                    progress_phase=phase,
                    activity_seen=activity_seen,
                    moonraker_request_in_flight=not submit_done.is_set(),
                )

                physical_complete = planner._completion_reached(plan, observed)
                if plan.get("action") == "unload":
                    physical_complete = (
                        physical_complete
                        and activity_seen
                        and submission_handled
                        and submission_acceptable
                    )

                if physical_complete:
                    planner._set_operation(
                        status="completed",
                        completed=True,
                        failed=False,
                        completed_at=core.timestamp_now(),
                        progress_phase="completed",
                        error=None,
                        observed=observed,
                    )
                    core.event_log(
                        "info",
                        "ifs_operation_completed_live_telemetry",
                        "Операция IFS подтверждена по состоянию принтера",
                        operation_id=operation_id,
                        action=plan.get("action"),
                        target_slot=plan.get("target_slot"),
                        moonraker_acknowledged=submission_handled
                        and submit_result.get("exception") is None,
                    )
                    return
            except Exception as exc:
                planner._set_operation(
                    telemetry_error=str(exc),
                    progress_phase="telemetry_retry",
                )

            time.sleep(planner.MONITOR_INTERVAL_SECONDS)

        _mark_failed(
            operation_id,
            "operation_monitor_timeout",
            "Истекло время ожидания подтверждения завершения операции",
            observed=last_observed,
        )


class LiveTelemetryRuntimeHandler(_BaseHandler):
    """Guarded prepare/execute API with concurrent live telemetry."""


planner._operation_worker = live_operation_worker
planner.RUNTIME_VERSION = RUNTIME_VERSION
persistent.RUNTIME_VERSION = RUNTIME_VERSION
runtime.RUNTIME_VERSION = RUNTIME_VERSION
local.RUNTIME_VERSION = RUNTIME_VERSION
control.RUNTIME_VERSION = RUNTIME_VERSION
writer.RUNTIME_VERSION = RUNTIME_VERSION
ui.RUNTIME_VERSION = RUNTIME_VERSION
core.APP_VERSION = RUNTIME_VERSION
core.Handler = LiveTelemetryRuntimeHandler


if __name__ == "__main__":
    core.main()
