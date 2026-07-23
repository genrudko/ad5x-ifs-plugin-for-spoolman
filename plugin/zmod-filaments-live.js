(() => {
  "use strict";

  const CONTROL_ID = "ifs-control-center";
  const STYLE_ID = "ifs-control-center-style";
  const MODAL_ID = "ifs-control-confirm-modal";
  const BUSY_STATUSES = new Set(["queued", "submitting", "running"]);
  const TERMINAL_STATUSES = new Set(["completed", "failed"]);
  const DIRTY_CLASS = "ifs-editor-dirty";
  const IDLE_POLL_MS = 10000;
  const BUSY_POLL_MS = 2000;

  const state = {
    metadata: null,
    presence: null,
    operation: null,
    lastOperationStatus: null,
    lastActiveSlot: null,
    pendingToken: null,
    pendingOperationId: null,
    requestRunning: false,
    stopped: false,
    dirty: false,
    timer: null,
    lastError: null
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
    const response = await fetch(path, {
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
      #${CONTROL_ID}{margin-top:10px;padding:12px 14px;border:1px solid var(--line);border-radius:14px;background:rgba(20,27,45,.94);box-shadow:var(--shadow)}
      #${CONTROL_ID} .ifsctl-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
      #${CONTROL_ID} .ifsctl-title{font-size:14px;font-weight:850}
      #${CONTROL_ID} .ifsctl-sub{margin-top:2px;color:var(--muted);font-size:10px}
      #${CONTROL_ID} .ifsctl-state{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid var(--line);border-radius:999px;font-size:10px;font-weight:800;color:var(--muted)}
      #${CONTROL_ID} .ifsctl-state:before{content:"";width:7px;height:7px;border-radius:50%;background:#72809b}
      #${CONTROL_ID} .ifsctl-state.running:before{background:var(--warn);box-shadow:0 0 0 3px rgba(245,196,81,.14)}
      #${CONTROL_ID} .ifsctl-state.completed:before{background:var(--ok);box-shadow:0 0 0 3px rgba(66,211,146,.14)}
      #${CONTROL_ID} .ifsctl-state.failed:before{background:var(--danger);box-shadow:0 0 0 3px rgba(255,107,122,.14)}
      #${CONTROL_ID} .ifsctl-body{display:grid;grid-template-columns:minmax(180px,1fr) minmax(240px,1.4fr);gap:12px;margin-top:10px}
      #${CONTROL_ID} .ifsctl-box{padding:10px;border:1px solid rgba(255,255,255,.07);border-radius:10px;background:rgba(255,255,255,.025)}
      #${CONTROL_ID} .ifsctl-label{color:var(--muted);font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}
      #${CONTROL_ID} .ifsctl-value{margin-top:3px;font-size:12px;font-weight:800}
      #${CONTROL_ID} .ifsctl-meta{margin-top:5px;color:var(--muted);font-size:10px;line-height:1.45}
      #${CONTROL_ID} .ifsctl-progress{height:6px;margin-top:8px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.08)}
      #${CONTROL_ID} .ifsctl-progress span{display:block;width:45%;height:100%;border-radius:inherit;background:var(--accent);animation:ifsctl-slide 1.25s ease-in-out infinite alternate}
      #${CONTROL_ID} .ifsctl-error{margin-top:8px;color:#ffc1c7;font-size:10px}
      .ifs-control-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.07)}
      .ifs-control-actions button{min-width:116px}
      .ifs-control-actions .ifs-control-danger{border-color:rgba(255,107,122,.42);color:#ffc1c7;background:rgba(255,107,122,.08)}
      .ifs-control-actions .ifs-control-primary{border-color:var(--accent);background:var(--accent);color:#fff}
      #${MODAL_ID}{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:18px;background:rgba(0,0,0,.62);backdrop-filter:blur(5px)}
      #${MODAL_ID} .ifsctl-dialog{width:min(590px,100%);max-height:min(760px,calc(100vh - 36px));overflow:auto;padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--panel);box-shadow:0 24px 80px rgba(0,0,0,.55)}
      #${MODAL_ID} h3{margin:0;font-size:17px}
      #${MODAL_ID} .ifsctl-warning{margin-top:10px;padding:9px 10px;border:1px solid rgba(245,196,81,.35);border-radius:10px;background:rgba(245,196,81,.08);color:#f7d982;font-size:11px;line-height:1.45}
      #${MODAL_ID} dl{display:grid;grid-template-columns:150px minmax(0,1fr);gap:7px 12px;margin:13px 0}
      #${MODAL_ID} dt{color:var(--muted);font-size:11px}
      #${MODAL_ID} dd{margin:0;font-size:11px;font-weight:750;overflow-wrap:anywhere}
      #${MODAL_ID} code{display:block;padding:9px;border:1px solid rgba(255,255,255,.07);border-radius:9px;background:#0d1424;color:#dce6ff;font-size:10px;white-space:pre-wrap;overflow-wrap:anywhere}
      #${MODAL_ID} .ifsctl-dialog-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}
      @keyframes ifsctl-slide{from{transform:translateX(-10%)}to{transform:translateX(125%)}}
      @media(max-width:760px){#${CONTROL_ID} .ifsctl-body{grid-template-columns:1fr}#${MODAL_ID} dl{grid-template-columns:1fr;gap:3px}#${MODAL_ID} dd{margin-bottom:7px}}
    `;
    document.head.appendChild(style);
  }

  function isBusy() {
    return !!(state.operation && BUSY_STATUSES.has(state.operation.status));
  }

  function phaseLabel(phase, status) {
    const labels = {
      dispatching: "Отправка команды",
      waiting_for_macro_activity: "Ожидание начала макроса",
      heating: "Нагрев экструдера",
      filament_change: "Смена филамента",
      waiting_for_slot_change: "Ожидание смены активного слота",
      finalizing: "Завершение операции",
      completed: "Операция завершена",
      failed: "Операция завершилась ошибкой",
      telemetry_retry: "Повтор чтения телеметрии"
    };
    if (labels[phase]) return labels[phase];
    if (status === "prepared") return "Операция подготовлена";
    if (status === "queued") return "Операция поставлена в очередь";
    if (status === "running" || status === "submitting") return "Операция выполняется";
    if (status === "completed") return "Операция завершена";
    if (status === "failed") return "Ошибка операции";
    return "Управление готово";
  }

  function operationClass(status) {
    if (BUSY_STATUSES.has(status)) return "running";
    if (status === "completed") return "completed";
    if (status === "failed") return "failed";
    return "";
  }

  function operationSummary() {
    const operation = state.operation || { status: "idle", observed: {} };
    const observed = operation.observed || {};
    const status = operation.status || "idle";
    const phase = phaseLabel(operation.progress_phase, status);
    const active = observed.active_slot != null
      ? observed.active_slot
      : state.metadata && state.metadata.active_slot;
    const target = operation.target_slot;
    const temperature = observed.extruder_temperature;
    const temperatureTarget = observed.extruder_target;
    const tempText = temperature != null
      ? `${Number(temperature).toFixed(1)} °C${temperatureTarget != null ? ` / ${Number(temperatureTarget).toFixed(0)} °C` : ""}`
      : "—";
    const routeText = operation.action
      ? `${operation.action === "unload" ? "Выгрузка" : "Смена"}${operation.active_slot_before != null ? ` · IFS ${operation.active_slot_before}` : ""}${target != null ? ` → IFS ${target}` : ""}`
      : "Команда не выполняется";
    return { operation, observed, status, phase, active, target, tempText, routeText };
  }

  function ensureControlCenter() {
    let panel = document.getElementById(CONTROL_ID);
    if (panel) return panel;
    const hero = document.querySelector("main .hero");
    const grid = document.getElementById("grid");
    if (!hero || !grid) return null;
    panel = document.createElement("section");
    panel.id = CONTROL_ID;
    hero.insertAdjacentElement("afterend", panel);
    return panel;
  }

  function renderControlCenter() {
    injectStyles();
    const panel = ensureControlCenter();
    if (!panel) return;
    const info = operationSummary();
    const error = info.operation.error && typeof info.operation.error === "object"
      ? info.operation.error.message || info.operation.error.code
      : state.lastError;
    panel.innerHTML = `
      <div class="ifsctl-head">
        <div>
          <div class="ifsctl-title">Управление IFS</div>
          <div class="ifsctl-sub">Двухфазное подтверждение и живая телеметрия операции</div>
        </div>
        <div class="ifsctl-state ${operationClass(info.status)}">${escapeHtml(info.phase)}</div>
      </div>
      <div class="ifsctl-body">
        <div class="ifsctl-box">
          <div class="ifsctl-label">Операция</div>
          <div class="ifsctl-value">${escapeHtml(info.routeText)}</div>
          <div class="ifsctl-meta">Активный слот: IFS ${escapeHtml(info.active == null ? "—" : info.active)}${info.operation.operation_id ? ` · ID ${escapeHtml(info.operation.operation_id)}` : ""}</div>
        </div>
        <div class="ifsctl-box">
          <div class="ifsctl-label">Телеметрия</div>
          <div class="ifsctl-value">${escapeHtml(info.phase)}</div>
          <div class="ifsctl-meta">Экструдер: ${escapeHtml(info.tempText)} · Moonraker: ${info.operation.moonraker_request_in_flight ? "команда выполняется" : info.operation.moonraker_acknowledged ? "подтверждено" : "ожидание"}</div>
          ${BUSY_STATUSES.has(info.status) ? '<div class="ifsctl-progress"><span></span></div>' : ""}
          ${error ? `<div class="ifsctl-error">${escapeHtml(error)}</div>` : ""}
        </div>
      </div>
    `;
  }

  function presenceFor(slot) {
    const item = state.presence && state.presence.slots
      ? state.presence.slots[String(slot)]
      : null;
    return item ? item.filament_present : null;
  }

  function injectSlotControls() {
    const activeSlot = Number(state.metadata && state.metadata.active_slot || 0);
    const busy = isBusy();
    document.querySelectorAll("#grid .slot[data-slot]").forEach(card => {
      const slot = Number(card.dataset.slot);
      let actions = card.querySelector(".ifs-control-actions");
      if (!actions) {
        actions = document.createElement("div");
        actions.className = "ifs-control-actions";
        card.appendChild(actions);
      }

      const present = presenceFor(slot);
      const isActive = slot === activeSlot;
      const enabled = !busy && (isActive || present === true);
      const label = isActive ? "Выгрузить" : present === true ? `Переключить на IFS ${slot}` : present === false ? "Филамент отсутствует" : "Состояние неизвестно";
      const action = isActive ? "unload" : "switch";
      actions.innerHTML = `<button type="button" class="${isActive ? "ifs-control-danger" : "ifs-control-primary"}" ${enabled ? "" : "disabled"}>${escapeHtml(label)}</button>`;
      const button = actions.querySelector("button");
      if (enabled) {
        button.addEventListener("click", () => beginOperation(action, slot));
      }
    });
  }

  function showConfirm(plan) {
    return new Promise(resolve => {
      document.getElementById(MODAL_ID)?.remove();
      const modal = document.createElement("div");
      modal.id = MODAL_ID;
      const actionLabel = plan.action === "unload" ? "Выгрузить филамент" : `Переключить на IFS ${plan.target_slot}`;
      modal.innerHTML = `
        <div class="ifsctl-dialog" role="dialog" aria-modal="true" aria-labelledby="ifsctl-dialog-title">
          <h3 id="ifsctl-dialog-title">${escapeHtml(actionLabel)}</h3>
          <div class="ifsctl-warning">Принтер выполнит перемещения, нагрев экструдера, подачу или выгрузку филамента и очистку сопла. Убедитесь, что рабочая зона свободна.</div>
          <dl>
            <dt>Текущий слот</dt><dd>IFS ${escapeHtml(plan.active_slot == null ? "—" : plan.active_slot)}</dd>
            <dt>Целевой слот</dt><dd>${plan.target_slot == null ? "Выгрузка без загрузки" : `IFS ${escapeHtml(plan.target_slot)}`}</dd>
            <dt>Материал</dt><dd>${escapeHtml(plan.material || "—")}</dd>
            <dt>Температура</dt><dd>${escapeHtml(plan.temperature == null ? "—" : `${plan.temperature} °C`)}</dd>
            <dt>Макрос</dt><dd>${escapeHtml(plan.macro || "—")}</dd>
          </dl>
          <code>${escapeHtml(plan.gcode_preview || "")}</code>
          <div class="ifsctl-dialog-actions">
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
      document.addEventListener("keydown", function onKey(event) {
        if (event.key === "Escape" && document.getElementById(MODAL_ID)) {
          document.removeEventListener("keydown", onKey);
          finish(false);
        }
      });
    });
  }

  async function beginOperation(action, slot) {
    if (isBusy()) return;
    state.lastError = null;
    renderControlCenter();
    injectSlotControls();
    try {
      const body = action === "unload" ? { action: "unload" } : { action: "switch", slot };
      const prepared = await request("/api/ifs/control/prepare", {
        method: "POST",
        body: JSON.stringify(body)
      });
      state.pendingToken = prepared.token;
      state.pendingOperationId = prepared.operation_id;
      const confirmed = await showConfirm(prepared.plan || {});
      if (!confirmed) {
        state.lastError = "Операция подготовлена, но выполнение отменено пользователем";
        renderControlCenter();
        return;
      }
      await request("/api/ifs/control/execute", {
        method: "POST",
        body: JSON.stringify({
          token: state.pendingToken,
          confirmation: prepared.confirmation_phrase || "EXECUTE_IFS_OPERATION"
        })
      });
      state.pendingToken = null;
      state.pendingOperationId = null;
      await refreshOperation(true);
    } catch (error) {
      state.lastError = error && error.message ? error.message : String(error);
      renderControlCenter();
      injectSlotControls();
    }
  }

  function setDirty(value) {
    state.dirty = !!value;
    document.documentElement.classList.toggle(DIRTY_CLASS, state.dirty);
  }

  function watchEditorChanges() {
    document.addEventListener("input", event => {
      if (event.target.closest("#grid .slot")) setDirty(true);
    }, true);
    document.addEventListener("change", event => {
      if (event.target.closest("#grid .slot")) setDirty(true);
    }, true);
    document.addEventListener("click", event => {
      if (event.target.closest("button.reset")) {
        window.setTimeout(() => setDirty(false), 0);
      } else if (event.target.closest("button.save")) {
        window.setTimeout(() => setDirty(false), 1500);
      }
    }, true);
  }

  async function refreshOperation(forceAll = false) {
    if (state.requestRunning || state.stopped || document.hidden) return;
    state.requestRunning = true;
    try {
      const operation = await request("/api/ifs/control/operation");
      const previousStatus = state.lastOperationStatus;
      state.operation = operation;
      state.lastOperationStatus = operation.status;
      state.lastError = null;

      const busy = BUSY_STATUSES.has(operation.status);
      if (forceAll || !busy || !state.metadata) {
        const [metadata, presence] = await Promise.all([
          request("/api/zmod/filaments"),
          request("/api/ifs/slots")
        ]);
        const activeSlot = Number(metadata && metadata.active_slot || 0);
        const activeChanged = state.lastActiveSlot != null && activeSlot > 0 && activeSlot !== state.lastActiveSlot;
        state.metadata = metadata;
        state.presence = presence;
        state.lastActiveSlot = activeSlot;
        if (activeChanged && !state.dirty && typeof window.load === "function") {
          window.setTimeout(() => window.load(), 250);
        }
      }

      if (BUSY_STATUSES.has(previousStatus) && TERMINAL_STATUSES.has(operation.status) && !state.dirty && typeof window.load === "function") {
        window.setTimeout(() => window.load(), 500);
      }
    } catch (error) {
      state.lastError = error && error.message ? error.message : String(error);
    } finally {
      state.requestRunning = false;
      renderControlCenter();
      injectSlotControls();
      schedule(isBusy() ? BUSY_POLL_MS : IDLE_POLL_MS);
    }
  }

  function schedule(delay) {
    window.clearTimeout(state.timer);
    if (!state.stopped) state.timer = window.setTimeout(() => refreshOperation(false), delay);
  }

  function start() {
    injectStyles();
    watchEditorChanges();
    renderControlCenter();
    const observer = new MutationObserver(() => {
      renderControlCenter();
      injectSlotControls();
    });
    const grid = document.getElementById("grid");
    if (grid) observer.observe(grid, { childList: true, subtree: true });
    refreshOperation(true);
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshOperation(true);
  });
  window.addEventListener("focus", () => refreshOperation(true));
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
