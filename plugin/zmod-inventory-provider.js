(() => {
  "use strict";

  const LABELS = {
    auto: "Авто",
    local: "Локальный",
    spoolman: "Spoolman",
    none: "Отключён"
  };

  const EFFECTIVE = {
    local: "Используется локальный источник",
    spoolman: "Используется Spoolman",
    none: "Учёт отключён"
  };

  let select;
  let stateText;
  let detailText;
  let busy = false;
  let timer = null;

  function addStyles() {
    const style = document.createElement("style");
    style.textContent = `
      .ifs-provider-panel{display:grid;grid-template-columns:auto minmax(150px,210px);align-items:center;gap:7px 12px;padding:11px 12px;border:1px solid var(--line);border-radius:14px;background:rgba(26,35,56,.72);min-width:300px}
      .ifs-provider-label{font-size:10px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
      .ifs-provider-select{height:36px!important;padding:0 9px!important;font-size:12px;font-weight:700}
      .ifs-provider-state{grid-column:1/-1;font-size:12px;font-weight:800;color:var(--text)}
      .ifs-provider-detail{grid-column:1/-1;font-size:11px;color:var(--muted);min-height:16px}
      .ifs-provider-panel.is-fallback{border-color:rgba(245,196,81,.52)}
      .ifs-provider-panel.is-error{border-color:rgba(255,107,122,.55)}
      @media(max-width:760px){.ifs-provider-panel{width:100%;min-width:0}}
    `;
    document.head.appendChild(style);
  }

  function buildPanel() {
    const hero = document.querySelector(".hero");
    const status = hero && hero.querySelector(".status");
    if (!hero || !status) return false;

    const panel = document.createElement("div");
    panel.className = "ifs-provider-panel";
    panel.innerHTML = `
      <label class="ifs-provider-label" for="ifs-provider-select">Источник учёта</label>
      <select class="ifs-provider-select" id="ifs-provider-select" aria-label="Источник учёта"></select>
      <div class="ifs-provider-state">Определение провайдера…</div>
      <div class="ifs-provider-detail"></div>
    `;

    status.insertAdjacentElement("beforebegin", panel);
    select = panel.querySelector("select");
    stateText = panel.querySelector(".ifs-provider-state");
    detailText = panel.querySelector(".ifs-provider-detail");
    select.addEventListener("change", changeProvider);
    return true;
  }

  async function request(path, options = {}) {
    const response = await fetch(path, { cache: "no-store", ...options });
    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      // The HTTP status below remains authoritative.
    }
    if (!response.ok) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  function render(status) {
    const panel = select.closest(".ifs-provider-panel");
    const supported = Array.isArray(status.supported_providers)
      ? status.supported_providers
      : ["auto", "spoolman", "none"];

    const currentOptions = Array.from(select.options).map(option => option.value).join(",");
    if (currentOptions !== supported.join(",")) {
      select.innerHTML = supported
        .map(provider => `<option value="${provider}">${LABELS[provider] || provider}</option>`)
        .join("");
    }

    select.value = status.configured_provider || "auto";
    stateText.textContent = EFFECTIVE[status.provider] || `Используется: ${status.provider || "неизвестно"}`;

    panel.classList.toggle("is-fallback", status.fallback_active === true);
    panel.classList.remove("is-error");

    if (status.fallback_active) {
      detailText.textContent = "Spoolman недоступен — автоматически включён локальный источник";
    } else if (status.provider === "local" && status.moonraker?.spoolman_connected) {
      detailText.textContent = "Локальный источник выбран вручную; Spoolman доступен";
    } else if (status.provider === "spoolman" && status.connected) {
      detailText.textContent = "Spoolman подключён через Moonraker";
    } else if (status.provider === "none") {
      detailText.textContent = "Синхронизация внешнего учёта отключена";
    } else {
      detailText.textContent = "";
    }
  }

  async function loadStatus() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      render(await request("/api/inventory/status"));
    } catch (error) {
      const panel = select.closest(".ifs-provider-panel");
      panel.classList.add("is-error");
      stateText.textContent = "Не удалось получить состояние провайдера";
      detailText.textContent = error.message;
    } finally {
      busy = false;
    }
  }

  async function changeProvider() {
    if (busy) return;
    const provider = select.value;
    busy = true;
    select.disabled = true;
    stateText.textContent = "Переключение…";
    detailText.textContent = "";
    try {
      const result = await request("/api/inventory/provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider })
      });
      render(result.inventory || await request("/api/inventory/status"));
    } catch (error) {
      stateText.textContent = "Переключение не выполнено";
      detailText.textContent = error.message;
      await loadStatus();
    } finally {
      busy = false;
      select.disabled = false;
    }
  }

  function schedule() {
    window.clearInterval(timer);
    timer = window.setInterval(loadStatus, 15000);
  }

  addStyles();
  if (!buildPanel()) return;
  loadStatus();
  schedule();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadStatus();
  });
  window.addEventListener("focus", loadStatus);
  window.addEventListener("beforeunload", () => window.clearInterval(timer));
})();
