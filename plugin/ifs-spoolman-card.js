(() => {
  "use strict";

  const VERSION = "2.0.0";
  const CARD_ID = "ifs-spoolman-fluidd-card";
  const STYLE_ID = "ifs-spoolman-fluidd-style";
  const COLLAPSE_KEY = "ad5xIfsManagerCollapsedV1";
  const API_BASE = `${location.protocol}//${location.hostname}:7913`;
  const MANAGE_URL = `${API_BASE}/`;

  const state = {
    status: null,
    spools: [],
    selectedSlot: 1,
    connected: false,
    lastError: null,
    collapsed: localStorage.getItem(COLLAPSE_KEY) === "true"
  };

  let observer = null;
  let refreshTimer = null;
  let lifecycleTimer = null;
  let lifecycleScheduled = false;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function visibleDashboardColumns() {
    return Array.from(
      document.querySelectorAll(".app-draggable.list-group")
    ).filter(column => {
      if (!column.isConnected) return false;
      const rect = column.getBoundingClientRect();
      const style = window.getComputedStyle(column);
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    });
  }

  function isDashboardActive() {
    return visibleDashboardColumns().length > 0;
  }

  function removeCard() {
    document.querySelectorAll(`#${CARD_ID}`).forEach(node => node.remove());
  }

  function findNativeCard(columns) {
    for (const column of columns) {
      const cards = Array.from(
        column.querySelectorAll(":scope > .v-card, :scope > .collapsable-card")
      );
      const spoolman = cards.find(card => {
        const text = String(card.textContent || "").toLowerCase();
        return text.includes("spoolman");
      });
      if (spoolman) return spoolman;
    }
    return null;
  }

  function createCard() {
    const columns = visibleDashboardColumns();
    if (!columns.length) return null;

    const anchor = findNativeCard(columns) || columns[0].firstElementChild;
    const card = document.createElement("div");
    card.id = CARD_ID;
    card.className = anchor && anchor.className
      ? `${anchor.className} ifssm-card`
      : "v-card collapsable-card ifssm-card";

    if (anchor && anchor.parentElement) {
      anchor.insertAdjacentElement("afterend", card);
    } else {
      columns[0].appendChild(card);
    }

    return card;
  }

  function ensureCard() {
    if (!isDashboardActive()) {
      removeCard();
      return null;
    }

    const cards = document.querySelectorAll(`#${CARD_ID}`);
    if (cards.length > 1) {
      Array.from(cards).slice(1).forEach(card => card.remove());
    }

    return cards[0] || createCard();
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CARD_ID}.ifssm-card {
        overflow: hidden;
        position: relative;
      }
      #${CARD_ID} .ifssm-header {
        min-height: 48px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 0 12px;
        border-bottom: 1px solid rgba(255,255,255,.08);
        cursor: pointer;
        user-select: none;
      }
      #${CARD_ID}.is-collapsed .ifssm-header {
        border-bottom: 0;
      }
      #${CARD_ID} .ifssm-heading {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 10px;
      }
      #${CARD_ID} .ifssm-icon {
        width: 23px;
        height: 23px;
        flex: 0 0 auto;
        opacity: .88;
      }
      #${CARD_ID} .ifssm-icon svg {
        display: block;
        width: 100%;
        height: 100%;
        fill: none;
        stroke: currentColor;
        stroke-width: 1.7;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      #${CARD_ID} .ifssm-title {
        font-size: 15px;
        font-weight: 500;
        line-height: 1.2;
      }
      #${CARD_ID} .ifssm-provider {
        margin-top: 2px;
        font-size: 11px;
        opacity: .58;
      }
      #${CARD_ID} .ifssm-header-actions {
        display: flex;
        align-items: center;
        gap: 7px;
      }
      #${CARD_ID} .ifssm-state {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 7px;
        border: 1px solid rgba(255,255,255,.09);
        border-radius: 999px;
        font-size: 10px;
        white-space: nowrap;
      }
      #${CARD_ID} .ifssm-state::before {
        content: "";
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #7d8594;
      }
      #${CARD_ID} .ifssm-state.connected::before {
        background: #2ecc71;
      }
      #${CARD_ID} .ifssm-collapse,
      #${CARD_ID} .ifssm-manage {
        width: 30px;
        height: 30px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: inherit;
        cursor: pointer;
        opacity: .72;
      }
      #${CARD_ID} .ifssm-collapse:hover,
      #${CARD_ID} .ifssm-manage:hover {
        background: rgba(255,255,255,.08);
        opacity: 1;
      }
      #${CARD_ID} .ifssm-collapse svg,
      #${CARD_ID} .ifssm-manage svg {
        width: 18px;
        height: 18px;
        fill: currentColor;
        transition: transform .16s ease;
      }
      #${CARD_ID}.is-collapsed .ifssm-collapse svg {
        transform: rotate(180deg);
      }
      #${CARD_ID} .ifssm-content {
        padding: 12px;
      }
      #${CARD_ID}.is-collapsed .ifssm-content {
        display: none;
      }
      #${CARD_ID} .ifssm-slots {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
      }
      #${CARD_ID} .ifssm-slot {
        min-width: 0;
        padding: 8px 6px;
        border: 1px solid rgba(255,255,255,.09);
        border-radius: 8px;
        background: rgba(255,255,255,.025);
        cursor: pointer;
        text-align: center;
      }
      #${CARD_ID} .ifssm-slot:hover {
        background: rgba(255,255,255,.055);
      }
      #${CARD_ID} .ifssm-slot.active {
        border-color: rgba(46,204,113,.68);
        box-shadow: inset 0 0 0 1px rgba(46,204,113,.14);
      }
      #${CARD_ID} .ifssm-slot.selected {
        background: rgba(33,150,243,.09);
      }
      #${CARD_ID} .ifssm-slot-number {
        font-size: 10px;
        opacity: .58;
      }
      #${CARD_ID} .ifssm-color {
        width: 25px;
        height: 25px;
        margin: 5px auto;
        border: 3px solid rgba(255,255,255,.18);
        border-radius: 50%;
        box-shadow: inset 0 0 0 1px rgba(0,0,0,.22);
      }
      #${CARD_ID} .ifssm-material {
        min-height: 13px;
        overflow: hidden;
        font-size: 11px;
        font-weight: 600;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #${CARD_ID} .ifssm-detail {
        margin-top: 10px;
        padding: 9px 10px;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 8px;
        font-size: 12px;
      }
      #${CARD_ID} .ifssm-detail-title {
        font-weight: 600;
      }
      #${CARD_ID} .ifssm-detail-meta {
        margin-top: 3px;
        opacity: .62;
      }
      #${CARD_ID} .ifssm-error {
        color: #ff8a80;
      }
      @media (max-width: 620px) {
        #${CARD_ID} .ifssm-state { display: none; }
        #${CARD_ID} .ifssm-slots { gap: 5px; }
      }
    `;
    document.head.appendChild(style);
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  function spoolMap() {
    const result = new Map();
    for (const spool of state.spools) {
      result.set(Number(spool.id), spool);
    }
    return result;
  }

  function assignments() {
    const raw = (state.status && state.status.assignments) || {};
    const result = {};
    for (let slot = 1; slot <= 4; slot += 1) {
      result[slot] = raw[String(slot)] == null
        ? null
        : Number(raw[String(slot)]);
    }
    return result;
  }

  function filamentOf(spool) {
    return spool && spool.filament ? spool.filament : {};
  }

  function materialOf(spool) {
    return filamentOf(spool).material || "—";
  }

  function colorOf(spool) {
    const raw = filamentOf(spool).color_hex || spool.color_hex || "777777";
    const value = String(raw).replace(/^#/, "");
    return /^[0-9a-f]{6}$/i.test(value) ? `#${value}` : "#777777";
  }

  function nameOf(spool) {
    const filament = filamentOf(spool);
    return filament.name || spool.name || `Катушка ${spool.id}`;
  }

  function vendorOf(spool) {
    const filament = filamentOf(spool);
    return filament.vendor && filament.vendor.name
      ? filament.vendor.name
      : "";
  }

  function renderSlots(slotAssignments, spools, activeSlot) {
    let html = "";
    for (let slot = 1; slot <= 4; slot += 1) {
      const spoolId = slotAssignments[slot];
      const spool = spoolId == null ? null : spools.get(spoolId);
      const classes = [
        "ifssm-slot",
        slot === activeSlot ? "active" : "",
        slot === state.selectedSlot ? "selected" : ""
      ].filter(Boolean).join(" ");

      html += `
        <button class="${classes}" type="button" data-slot="${slot}">
          <div class="ifssm-slot-number">Слот ${slot}</div>
          <div class="ifssm-color" style="background:${colorOf(spool)}"></div>
          <div class="ifssm-material">${escapeHtml(materialOf(spool))}</div>
        </button>
      `;
    }
    return html;
  }

  function renderDetail(slotAssignments, spools, activeSlot) {
    const spoolId = slotAssignments[state.selectedSlot];
    const spool = spoolId == null ? null : spools.get(spoolId);

    if (!spool) {
      return `
        <div class="ifssm-detail-title">Слот ${state.selectedSlot}</div>
        <div class="ifssm-detail-meta">
          Катушка не назначена${state.selectedSlot === activeSlot ? " · активный слот" : ""}
        </div>
      `;
    }

    const vendor = vendorOf(spool);
    return `
      <div class="ifssm-detail-title">${escapeHtml(nameOf(spool))}</div>
      <div class="ifssm-detail-meta">
        Слот ${state.selectedSlot} · ${escapeHtml(materialOf(spool))}
        ${vendor ? ` · ${escapeHtml(vendor)}` : ""}
        ${state.selectedSlot === activeSlot ? " · активный" : ""}
      </div>
    `;
  }

  function render() {
    injectStyles();
    const card = ensureCard();
    if (!card) return;

    const slotAssignments = assignments();
    const spools = spoolMap();
    const activeSlot = Number((state.status && state.status.active_slot) || 1);
    if (!Number.isInteger(state.selectedSlot) || state.selectedSlot < 1 || state.selectedSlot > 4) {
      state.selectedSlot = activeSlot;
    }

    card.classList.toggle("is-collapsed", state.collapsed);
    card.innerHTML = `
      <div class="ifssm-header" role="button" tabindex="0" aria-expanded="${!state.collapsed}">
        <div class="ifssm-heading">
          <span class="ifssm-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <circle cx="8" cy="10" r="6"></circle>
              <circle cx="8" cy="10" r="2"></circle>
              <path d="M8 16v2h8M16 15v6M16 15h3M16 18h2M16 21h3"></path>
            </svg>
          </span>
          <div>
            <div class="ifssm-title">AD5X IFS Manager</div>
            <div class="ifssm-provider">Учёт катушек: ${state.connected ? "Spoolman" : "не подключён"}</div>
          </div>
        </div>
        <div class="ifssm-header-actions">
          <span class="ifssm-state ${state.connected ? "connected" : ""}">
            ${state.connected ? "Связь есть" : "Нет связи"}
          </span>
          <button class="ifssm-manage" type="button" title="Открыть управление" aria-label="Открыть управление">
            <svg viewBox="0 0 24 24"><path d="M19.4 13a7.4 7.4 0 0 0 0-2l2-1.6-2-3.4-2.4 1a8 8 0 0 0-1.7-1L15 3.4h-4L10.6 6a8 8 0 0 0-1.7 1L6.5 6 4.5 9.4l2 1.6a7.4 7.4 0 0 0 0 2l-2 1.6 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.4 2.6h4l.4-2.6a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2.1-1.6ZM13 15.5A3.5 3.5 0 1 1 13 8a3.5 3.5 0 0 1 0 7.5Z"></path></svg>
          </button>
          <button class="ifssm-collapse" type="button" title="${state.collapsed ? "Развернуть" : "Свернуть"}" aria-label="${state.collapsed ? "Развернуть" : "Свернуть"}">
            <svg viewBox="0 0 24 24"><path d="m7 14 5-5 5 5z"></path></svg>
          </button>
        </div>
      </div>
      <div class="ifssm-content">
        <div class="ifssm-slots">
          ${renderSlots(slotAssignments, spools, activeSlot)}
        </div>
        <div class="ifssm-detail">
          ${renderDetail(slotAssignments, spools, activeSlot)}
          ${state.lastError ? `<div class="ifssm-detail-meta ifssm-error">Ошибка: ${escapeHtml(state.lastError)}</div>` : ""}
        </div>
      </div>
    `;

    const header = card.querySelector(".ifssm-header");
    const toggle = () => {
      state.collapsed = !state.collapsed;
      localStorage.setItem(COLLAPSE_KEY, String(state.collapsed));
      render();
    };

    header.addEventListener("click", event => {
      if (event.target.closest("button")) return;
      toggle();
    });
    header.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
    });

    card.querySelector(".ifssm-collapse").addEventListener("click", toggle);
    card.querySelector(".ifssm-manage").addEventListener("click", () => {
      window.open(MANAGE_URL, "_blank", "noopener");
    });
    card.querySelectorAll("[data-slot]").forEach(button => {
      button.addEventListener("click", () => {
        state.selectedSlot = Number(button.dataset.slot);
        render();
      });
    });
  }

  async function refreshData() {
    if (!isDashboardActive()) return;

    try {
      const [status, spools] = await Promise.all([
        fetchJson(`${API_BASE}/api/status`),
        fetchJson(`${API_BASE}/api/spools`)
      ]);
      state.status = status || null;
      state.spools = Array.isArray(spools) ? spools : [];
      state.connected = Boolean(status && status.spoolman_connected);
      state.lastError = null;
      if (!state.selectedSlot) {
        state.selectedSlot = Number(status && status.active_slot) || 1;
      }
    } catch (error) {
      state.connected = false;
      state.lastError = error && error.message ? error.message : String(error);
    }

    render();
  }

  function lifecycle() {
    lifecycleScheduled = false;

    if (!isDashboardActive()) {
      removeCard();
      return;
    }

    render();
  }

  function scheduleLifecycle() {
    if (lifecycleScheduled) return;
    lifecycleScheduled = true;
    window.setTimeout(lifecycle, 100);
  }

  function start() {
    injectStyles();
    lifecycle();
    refreshData();

    observer = new MutationObserver(scheduleLifecycle);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style"]
    });

    window.addEventListener("hashchange", scheduleLifecycle);
    window.addEventListener("popstate", scheduleLifecycle);
    window.addEventListener("resize", scheduleLifecycle);

    refreshTimer = window.setInterval(refreshData, 15000);
    lifecycleTimer = window.setInterval(lifecycle, 1500);

    window.addEventListener("beforeunload", () => {
      if (observer) observer.disconnect();
      if (refreshTimer !== null) clearInterval(refreshTimer);
      if (lifecycleTimer !== null) clearInterval(lifecycleTimer);
    });

    console.info(`AD5X IFS Manager Fluidd card v${VERSION} loaded`);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
