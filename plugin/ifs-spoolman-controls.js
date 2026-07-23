(() => {
  "use strict";

  const CARD_ID = "ifs-spoolman-fluidd-card";
  const PANEL_ID = "ifs-spoolman-control-panel";
  const STYLE_ID = "ifs-spoolman-control-style";
  const MODAL_ID = "ifs-spoolman-control-modal";
  const API_BASE = `${location.protocol}//${location.hostname}:7913`;
  const MANAGER_URL = `${API_BASE}/manager`;
  const BUSY_STATUSES = new Set(["queued", "submitting", "running"]);
  const TERMINAL_STATUSES = new Set(["completed", "failed"]);

  const state = {
    status: null,
    presence: null,
    operation: null,
    pendingToken: null,
    lastOperationStatus: null,
    lastError: null,
    requestRunning: false,
    refreshQueued: false,
    refreshQueuedForceAll: false,
    stopped: false,
    timer: null
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function errorMessage(payload, fallback) {
    const error = payload && payload.error;
    if (error && typeof error === "object") {
      return error.message || error.code || fallback;
    }
    if (typeof error === "string" && error) return error;
    return fallback;
  }

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      }
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }
    if (!response.ok) {
      const error = payload && payload.error;
      const exc = new Error(errorMessage(payload, `HTTP ${response.status}`));
      exc.code = error && typeof error === "object" ? error.code : null;
      exc.details = error && typeof error === "object" ? error.details : null;
      exc.status = response.status;
      throw exc;
    }
    return payload;
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CARD_ID} #${PANEL_ID}{margin-top:8px;padding:9px 10px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.025)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
      #${CARD_ID} #${PANEL_ID} .ifsfc-title{font-size:11px;font-weight:800}
      #${CARD_ID} #${PANEL_ID} .ifsfc-state{display:inline-flex;align-items:center;gap:5px;padding:2px 7px;border:1px solid rgba(255,255,255,.08);border-radius:999px;font-size:9px;font-weight:800;color:rgba(255,255,255,.62)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-state:before{content:"";width:6px;height:6px;border-radius:50%;background:#7d8594}
      #${CARD_ID} #${PANEL_ID} .ifsfc-state.running:before{background:#f5c451;box-shadow:0 0 0 3px rgba(245,196,81,.13)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-state.completed:before{background:#2ecc71;box-shadow:0 0 0 3px rgba(46,204,113,.13)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-state.failed:before{background:#ff6b7a;box-shadow:0 0 0 3px rgba(255,107,122,.13)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-line{margin-top:6px;font-size:10px;color:rgba(255,255,255,.58);line-height:1.4}
      #${CARD_ID} #${PANEL_ID} .ifsfc-line strong{color:inherit}
      #${CARD_ID} #${PANEL_ID} .ifsfc-actions{display:flex;gap:6px;margin-top:8px}
      #${CARD_ID} #${PANEL_ID} .ifsfc-actions button{flex:1;height:30px;border-radius:8px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.045);color:inherit;font-size:10px;font-weight:800;cursor:pointer}
      #${CARD_ID} #${PANEL_ID} .ifsfc-actions button.primary{border-color:rgba(90,120,255,.36);background:rgba(90,120,255,.18);color:#dbe5ff}
      #${CARD_ID} #${PANEL_ID} .ifsfc-actions button.danger{border-color:rgba(255,107,122,.34);background:rgba(255,107,122,.11);color:#ffc1c7}
      #${CARD_ID} #${PANEL_ID} .ifsfc-actions button:disabled{opacity:.45;cursor:not-allowed}
      #${CARD_ID} #${PANEL_ID} .ifsfc-progress{height:5px;margin-top:7px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.08)}
      #${CARD_ID} #${PANEL_ID} .ifsfc-progress span{display:block;width:42%;height:100%;border-radius:inherit;background:#5a78ff;animation:ifsfc-slide 1.2s ease-in-out infinite alternate}
      #${CARD_ID} #${PANEL_ID} .ifsfc-error{margin-top:6px;color:#ffc1c7;font-size:9px}
      #${MODAL_ID}{position:fixed;inset:0;z-index:100000;display:grid;place-items:center;padding:18px;background:rgba(0,0,0,.66);backdrop-filter:blur(5px)}
      #${MODAL_ID} .ifsfc-dialog{width:min(560px,100%);max-height:min(720px,calc(100vh - 36px));overflow:auto;padding:16px;border:1px solid rgba(255,255,255,.12);border-radius:16px;background:#151b29;color:#edf2ff;box-shadow:0 26px 90px rgba(0,0,0,.6);font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
      #${MODAL_ID} h3{margin:0;font-size:17px}
      #${MODAL_ID} .ifsfc-warning{margin-top:10px;padding:9px 10px;border:1px solid rgba(245,196,81,.35);border-radius:10px;background:rgba(245,196,81,.08);color:#f7d982;font-size:11px}
      #${MODAL_ID} dl{display:grid;grid-template-columns:145px minmax(0,1fr);gap:7px 12px;margin:13px 0}
      #${MODAL_ID} dt{color:#9eabc4;font-size:11px}
      #${MODAL_ID} dd{margin:0;font-size:11px;font-weight:750;overflow-wrap:anywhere}
      #${MODAL_ID} code{display:block;padding:9px;border:1px solid rgba(255,255,255,.07);border-radius:9px;background:#0d1424;color:#dce6ff;font-size:10px;white-space:pre-wrap;overflow-wrap:anywhere}
      #${MODAL_ID} .ifsfc-dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
      #${MODAL_ID} button{height:34px;padding:0 12px;border:1px solid rgba(255,255,255,.12);border-radius:9px;background:#20293b;color:#edf2ff;font-weight:800;cursor:pointer}
      #${MODAL_ID} button.primary{border-color:#5a78ff;background:#5a78ff;color:#fff}
      @keyframes ifsfc-slide{from{transform:translateX(-12%)}to{transform:translateX(138%)}}
      @media(max-width:600px){#${MODAL_ID} dl{grid-template-columns:1fr;gap:3px}#${MODAL_ID} dd{margin-bottom:7px}}
    `;
    document.head.appendChild(style);
  }

  function selectedSlot() {
    const selected = document.querySelector(`#${CARD_ID} .ifssm-slot.is-selected[data-slot]`);
    if (selected) return Number(selected.dataset.slot || 0);
    const active = Number(state.status && state.status.active_slot || 0);
    return active || 1;
  }

  function activeSlot() {
    return Number(state.status && state.status.active_slot || 0);
  }

  function presenceFor(slot) {
    const item = state.presence && state.presence.slots
      ? state.presence.slots[String(slot)]
      : null;
    return item ? item.filament_present : null;
  }

  function isBusy() {
    return !!(state.operation && BUSY_STATUSES.has(state.operation.status));
  }

  function phaseLabel(phase, status) {
    const labels = {
      dispatching: "Команда принята",
      waiting_for_macro_activity: "Ожидание макроса",
      heating: "Нагрев",
      filament_change: "Смена филамента",
      waiting_for_slot_change: "Ожидание смены слота",
      finalizing: "Завершение",
      completed: "Завершено",
      failed: "Ошибка",
      telemetry_retry: "Повтор телеметрии"
    };
    if (labels[phase]) return labels[phase];
    if (status === "prepared") return "Подготовлено";
    if (status === "queued") return "Команда принята";
    if (status === "running" || status === "submitting") return "Выполняется";
    if (status === "completed") return "Завершено";
    if (status === "failed") return "Ошибка";
    return "Готово";
  }

  function statusClass(status) {
    if (BUSY_STATUSES.has(status)) return "running";
    if (status === "completed") return "completed";
    if (status === "failed") return "failed";
    return "";
  }

  function moonrakerLabel(operation, status) {
    if (BUSY_STATUSES.has(status)) {
      if (operation.moonraker_request_in_flight) return "команда выполняется";
      if (operation.moonraker_acknowledged) return "подтверждено";
      return "команда принята";
    }
    if (operation.moonraker_acknowledged) return "подтверждено";
    return "нет активной команды";
  }

  function stabilizeCardHeader(busy) {
    if (!busy) return;
    const badge = document.querySelector(`#${CARD_ID} .ifssm-status`);
    if (!badge) return;
    badge.classList.add("connected");
    badge.textContent = "Операция выполняется";
  }

  function ensurePanel() {
    const card = document.getElementById(CARD_ID);
    if (!card) return null;
    let panel = card.querySelector(`#${PANEL_ID}`);
    if (panel) return panel;
    const detail = card.querySelector(".ifssm-detail");
    if (!detail) return null;
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    detail.insertAdjacentElement("afterend", panel);
    return panel;
  }

  function renderPanel() {
    injectStyles();
    const panel = ensurePanel();
    if (!panel) return;
    const operation = state.operation || { status: "idle", observed: {} };
    const observed = operation.observed || {};
    const status = operation.status || "idle";
    const selected = selectedSlot();
    const active = activeSlot();
    const present = presenceFor(selected);
    const busy = BUSY_STATUSES.has(status);
    const isActive = selected === active;
    const enabled = !busy && (isActive || present === true);
    const actionLabel = isActive
      ? "Выгрузить"
      : present === true
        ? `Переключить на IFS ${selected}`
        : present === false
          ? "Филамент отсутствует"
          : "Состояние неизвестно";
    const phase = phaseLabel(operation.progress_phase, status);
    const temp = observed.extruder_temperature;
    const target = observed.extruder_target;
    const tempText = temp != null
      ? `${Number(temp).toFixed(1)} °C${target != null ? ` / ${Number(target).toFixed(0)} °C` : ""}`
      : "—";
    const error = operation.error && typeof operation.error === "object"
      ? operation.error.message || operation.error.code
      : state.lastError;
    const route = operation.action
      ? `${operation.action === "unload" ? "Выгрузка" : "Смена"}${operation.active_slot_before != null ? ` · IFS ${operation.active_slot_before}` : ""}${operation.target_slot != null ? ` → IFS ${operation.target_slot}` : ""}`
      : `Выбран IFS ${selected} · активен IFS ${active || "—"}`;

    stabilizeCardHeader(busy);
    panel.innerHTML = `
      <div class="ifsfc-head">
        <div class="ifsfc-title">Управление IFS</div>
        <div class="ifsfc-state ${statusClass(status)}">${escapeHtml(phase)}</div>
      </div>
      <div class="ifsfc-line"><strong>${escapeHtml(route)}</strong> · Экструдер ${escapeHtml(tempText)} · Moonraker: ${escapeHtml(moonrakerLabel(operation, status))}</div>
      ${busy ? '<div class="ifsfc-progress"><span></span></div>' : ""}
      ${error ? `<div class="ifsfc-error">${escapeHtml(error)}</div>` : ""}
      <div class="ifsfc-actions">
        <button type="button" class="${isActive ? "danger" : "primary"}" data-ifs-action="${isActive ? "unload" : "switch"}" data-slot="${selected}" ${enabled ? "" : "disabled"}>${escapeHtml(actionLabel)}</button>
        <button type="button" data-open-manager>Подробнее</button>
      </div>
    `;

    const action = panel.querySelector("button[data-ifs-action]");
    if (action && enabled) {
      action.addEventListener("click", () => beginOperation(action.dataset.ifsAction, Number(action.dataset.slot)));
    }
    panel.querySelector("button[data-open-manager]")?.addEventListener("click", () => {
      window.open(MANAGER_URL, "_blank", "noopener");
    });
  }

  function showConfirm(plan) {
    return new Promise(resolve => {
      document.getElementById(MODAL_ID)?.remove();
      const modal = document.createElement("div");
      modal.id = MODAL_ID;
      const actionLabel = plan.action === "unload"
        ? "Выгрузить филамент"
        : `Переключить на IFS ${plan.target_slot}`;
      modal.innerHTML = `
        <div class="ifsfc-dialog" role="dialog" aria-modal="true" aria-labelledby="ifsfc-title">
          <h3 id="ifsfc-title">${escapeHtml(actionLabel)}</h3>
          <div class="ifsfc-warning">Принтер выполнит перемещения, нагрев, подачу или выгрузку филамента и очистку сопла. Температура выгрузки старого филамента определяется внутренним алгоритмом макроса. Убедитесь, что рабочая зона свободна.</div>
          <dl>
            <dt>Текущий слот</dt><dd>IFS ${escapeHtml(plan.active_slot == null ? "—" : plan.active_slot)}</dd>
            <dt>Целевой слот</dt><dd>${plan.target_slot == null ? "Выгрузка без загрузки" : `IFS ${escapeHtml(plan.target_slot)}`}</dd>
            <dt>Материал</dt><dd>${escapeHtml(plan.material || "—")}</dd>
            <dt>Температура загрузки</dt><dd>${escapeHtml(plan.temperature == null ? "—" : `${plan.temperature} °C`)}</dd>
            <dt>Макрос</dt><dd>${escapeHtml(plan.macro || "—")}</dd>
          </dl>
          <code>${escapeHtml(plan.gcode_preview || "")}</code>
          <div class="ifsfc-dialog-actions">
            <button type="button" data-result="cancel">Отмена</button>
            <button type="button" class="primary" data-result="confirm">Подтвердить и выполнить</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
      const finish = result => {
        modal.remove();
        resolve(result);
      };
      modal.addEventListener("click", event => {
        const button = event.target.closest("button[data-result]");
        if (button) finish(button.dataset.result === "confirm");
        else if (event.target === modal) finish(false);
      });
    });
  }

  function optimisticQueuedOperation(prepared, accepted) {
    const plan = prepared.plan || {};
    return {
      operation_id: accepted.operation_id || prepared.operation_id || null,
      status: "queued",
      accepted: true,
      gcode_submitted: false,
      completed: false,
      failed: false,
      action: plan.action || null,
      active_slot_before: plan.active_slot == null ? activeSlot() : plan.active_slot,
      target_slot: plan.target_slot == null ? null : plan.target_slot,
      gcode: accepted.gcode || plan.gcode_preview || null,
      plan,
      observed: {},
      progress_phase: "dispatching",
      moonraker_request_in_flight: false,
      moonraker_acknowledged: false,
      error: null,
      optimistic: true
    };
  }

  async function beginOperation(action, slot) {
    if (isBusy()) return;
    state.lastError = null;
    renderPanel();
    try {
      const body = action === "unload" ? { action: "unload" } : { action: "switch", slot };
      const prepared = await request("/api/ifs/control/prepare", {
        method: "POST",
        body: JSON.stringify(body)
      });
      state.pendingToken = prepared.token;
      const confirmed = await showConfirm(prepared.plan || {});
      if (!confirmed) {
        state.pendingToken = null;
        state.lastError = "Выполнение отменено пользователем";
        renderPanel();
        return;
      }
      const accepted = await request("/api/ifs/control/execute", {
        method: "POST",
        body: JSON.stringify({
          token: state.pendingToken,
          confirmation: prepared.confirmation_phrase || "EXECUTE_IFS_OPERATION"
        })
      });
      state.pendingToken = null;
      state.operation = optimisticQueuedOperation(prepared, accepted);
      state.lastOperationStatus = "queued";
      state.lastError = null;
      renderPanel();
      window.clearTimeout(state.timer);
      refresh(true);
    } catch (error) {
      state.pendingToken = null;
      state.lastError = error && error.message ? error.message : String(error);
      renderPanel();
    }
  }

  async function refresh(forceAll = false) {
    if (state.stopped || document.hidden) return;
    if (state.requestRunning) {
      state.refreshQueued = true;
      state.refreshQueuedForceAll = state.refreshQueuedForceAll || forceAll;
      return;
    }
    state.requestRunning = true;
    try {
      const operation = await request("/api/ifs/control/operation");
      const previous = state.lastOperationStatus;
      state.operation = operation;
      state.lastOperationStatus = operation.status;
      state.lastError = null;
      const busy = BUSY_STATUSES.has(operation.status);
      if (forceAll || !busy || !state.status) {
        const [status, presence] = await Promise.all([
          request("/api/status"),
          request("/api/ifs/slots")
        ]);
        state.status = status;
        state.presence = presence;
      }
      if (BUSY_STATUSES.has(previous) && TERMINAL_STATUSES.has(operation.status)) {
        window.setTimeout(() => refresh(true), 750);
      }
    } catch (error) {
      state.lastError = error && error.message ? error.message : String(error);
    } finally {
      state.requestRunning = false;
      renderPanel();
      if (state.refreshQueued) {
        const queuedForceAll = state.refreshQueuedForceAll;
        state.refreshQueued = false;
        state.refreshQueuedForceAll = false;
        window.clearTimeout(state.timer);
        state.timer = window.setTimeout(() => refresh(queuedForceAll), 0);
      } else {
        schedule(isBusy() ? 2000 : 8000);
      }
    }
  }

  function schedule(delay) {
    window.clearTimeout(state.timer);
    if (!state.stopped) state.timer = window.setTimeout(() => refresh(false), delay);
  }

  function start() {
    injectStyles();
    const observer = new MutationObserver(() => {
      if (!document.querySelector(`#${CARD_ID} #${PANEL_ID}`)) {
        renderPanel();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("click", event => {
      const manage = event.target && event.target.closest
        ? event.target.closest(`#${CARD_ID} .ifssm-manage`)
        : null;
      if (!manage) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      window.open(MANAGER_URL, "_blank", "noopener");
    }, true);
    refresh(true);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh(true);
  });
  window.addEventListener("focus", () => refresh(true));
  window.addEventListener("beforeunload", () => {
    state.stopped = true;
    window.clearTimeout(state.timer);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
