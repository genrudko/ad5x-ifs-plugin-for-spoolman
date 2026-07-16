(() => {
  "use strict";

  const CARD_ID = "ifs-spoolman-fluidd-card";
  const STYLE_ID = "ifs-spoolman-fluidd-style";
  const API_BASE = `${location.protocol}//${location.hostname}:7913`;
  const MANAGE_URL = `${location.protocol}//${location.hostname}:7913/`;

  const state = {
    status: null,
    spools: [],
    selectedSlot: null,
    connected: false,
    lastError: null
  };

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CARD_ID}.ifssm-card {
        overflow: hidden;
      }

      #${CARD_ID} .ifssm-wrap {
        padding: 10px 12px 12px;
      }

      #${CARD_ID} .ifssm-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        min-height: 48px;
        margin: -10px -12px 10px;
        padding: 7px 10px 7px 12px;
        border-bottom:
          1px solid var(--ifssm-header-border, rgba(255,255,255,.10));
        background:
          var(--ifssm-header-background, rgba(255,255,255,.045));
        color: var(--ifssm-header-color, inherit);
      }

      #${CARD_ID} .ifssm-head-left {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
      }

      /* IFS_SPOOLMAN_FLUIDD_ICON_V1 */
      #${CARD_ID} .ifssm-brand-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        width: 23px;
        height: 23px;
        color: inherit;
        opacity: .88;
      }

      #${CARD_ID} .ifssm-brand-icon svg {
        display: block;
        width: 22px;
        height: 22px;
        overflow: visible;
      }

      #${CARD_ID} .ifssm-brand-icon .ifs-icon-line {
        fill: none;
        stroke: currentColor;
        stroke-width: 1.65;
        stroke-linecap: round;
        stroke-linejoin: round;
      }

      #${CARD_ID} .ifssm-brand-icon .ifs-icon-fill {
        fill: currentColor;
        stroke: none;
      }

      #${CARD_ID} .ifssm-title {
        font-size: 15px;
        font-weight: 700;
        line-height: 1.2;
        color: var(--ifssm-header-color, inherit);
      }

      #${CARD_ID} .ifssm-sub {
        font-size: 11px;
        color: rgba(255,255,255,.58);
        margin-top: 2px;
      }

      #${CARD_ID} .ifssm-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(255,255,255,.03);
        color: inherit;
      }

      #${CARD_ID} .ifssm-status::before {
        content: "";
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #7d8594;
        box-shadow: 0 0 0 3px rgba(125,133,148,.14);
      }

      #${CARD_ID} .ifssm-status.connected::before {
        background: #2ecc71;
        box-shadow: 0 0 0 3px rgba(46,204,113,.16);
      }

      #${CARD_ID} .ifssm-manage {
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(255,255,255,.04);
        color: inherit;
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 11px;
        font-weight: 700;
        cursor: pointer;
        transition: .15s ease;
      }

      #${CARD_ID} .ifssm-manage:hover {
        background: rgba(255,255,255,.08);
      }

      #${CARD_ID} .ifssm-slots {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 8px;
        margin-bottom: 10px;
      }

      #${CARD_ID} .ifssm-slot {
        position: relative;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(255,255,255,.03);
        padding: 8px 6px 7px;
        cursor: pointer;
        transition: .15s ease;
        min-width: 0;
      }

      #${CARD_ID} .ifssm-slot:hover {
        background: rgba(255,255,255,.05);
      }

      #${CARD_ID} .ifssm-slot.is-selected {
        border-color: rgba(40,185,92,.8);
        box-shadow: inset 0 0 0 1px rgba(40,185,92,.18);
        background: rgba(40,185,92,.08);
      }

      #${CARD_ID} .ifssm-slot-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
      }

      #${CARD_ID} .ifssm-slot-num {
        width: 18px;
        height: 18px;
        border-radius: 6px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        font-weight: 700;
        background: rgba(255,255,255,.08);
        color: inherit;
        flex: 0 0 auto;
      }

      #${CARD_ID} .ifssm-slot.is-selected .ifssm-slot-num {
        background: rgba(40,185,92,.18);
        color: #7ef1ab;
      }

      #${CARD_ID} .ifssm-slot-body {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 5px;
      }

      #${CARD_ID} .ifssm-slot-material {
        font-size: 11px;
        font-weight: 700;
        color: inherit;
        line-height: 1;
        min-height: 12px;
      }

      #${CARD_ID} .ifssm-slot.unassigned .ifssm-slot-material {
        color: rgba(255,255,255,.40);
      }

      #${CARD_ID} .ifssm-detail {
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 10px;
        background: rgba(255,255,255,.03);
        padding: 10px;
      }

      #${CARD_ID} .ifssm-detail-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 8px;
      }

      #${CARD_ID} .ifssm-name {
        font-size: 14px;
        font-weight: 700;
        line-height: 1.2;
        color: inherit;
        word-break: break-word;
      }

      #${CARD_ID} .ifssm-meta {
        margin-top: 3px;
        font-size: 11px;
        color: rgba(255,255,255,.56);
      }

      #${CARD_ID} .ifssm-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        justify-content: flex-end;
      }

      #${CARD_ID} .ifssm-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 2px 7px;
        font-size: 10px;
        font-weight: 700;
        line-height: 1.2;
        border: 1px solid rgba(255,255,255,.08);
        background: rgba(255,255,255,.04);
        color: inherit;
      }

      #${CARD_ID} .ifssm-badge.accent {
        background: rgba(90,120,255,.14);
        color: #b7c7ff;
        border-color: rgba(90,120,255,.18);
      }

      #${CARD_ID} .ifssm-row {
        display: grid;
        grid-template-columns: 52px minmax(0, 1fr);
        gap: 10px;
        align-items: center;
      }

      #${CARD_ID} .ifssm-progress-label {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 5px;
        font-size: 11px;
        color: rgba(255,255,255,.60);
      }

      #${CARD_ID} .ifssm-progress-value {
        font-weight: 700;
        color: inherit;
      }

      #${CARD_ID} .ifssm-progress {
        height: 7px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(255,255,255,.08);
      }

      #${CARD_ID} .ifssm-progress > span {
        display: block;
        height: 100%;
        border-radius: inherit;
      }

      #${CARD_ID} .ifssm-empty {
        font-size: 12px;
        color: rgba(255,255,255,.56);
        line-height: 1.45;
      }

      #${CARD_ID} .ifssm-footer {
        margin-top: 8px;
        font-size: 10px;
        color: rgba(255,255,255,.42);
      }

      #${CARD_ID} .ifssm-icon {
        position: relative;
        border-radius: 50%;
        flex: 0 0 auto;
      }

      #${CARD_ID} .ifssm-icon.small {
        width: 34px;
        height: 34px;
      }

      #${CARD_ID} .ifssm-icon.large {
        width: 46px;
        height: 46px;
      }

      #${CARD_ID} .ifssm-icon-rim {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background:
          radial-gradient(
            circle at center,
            rgba(255,255,255,.08) 0 58%,
            rgba(0,0,0,.10) 76%,
            rgba(0,0,0,.22) 100%
          );
        box-shadow:
          inset 0 0 0 1px rgba(255,255,255,.10),
          inset 0 0 0 3px rgba(0,0,0,.06);
        pointer-events: none;
      }

      #${CARD_ID} .ifssm-icon-winding {
        position: absolute;
        inset: 4px;
        overflow: hidden;
        border-radius: 50%;
        box-shadow:
          inset 0 0 0 1px rgba(255,255,255,.10),
          inset 0 0 0 2px rgba(0,0,0,.06);
      }

      #${CARD_ID} .ifssm-icon::after {
        content: "";
        position: absolute;
        inset: 5px;
        border-radius: 50%;
        background:
          repeating-radial-gradient(
            circle at center,
            rgba(255,255,255,.08) 0 1px,
            transparent 1px 4px
          );
        opacity: .22;
        pointer-events: none;
      }

      #${CARD_ID} .ifssm-icon-hub {
        position: absolute;
        inset: 11px;
        border-radius: 50%;
        background:
          linear-gradient(180deg, rgba(255,255,255,.16), rgba(0,0,0,.24)),
          #2b3444;
        box-shadow:
          inset 0 0 0 1px rgba(255,255,255,.08),
          inset 0 -2px 5px rgba(0,0,0,.25);
      }

      #${CARD_ID} .ifssm-icon-hole {
        position: absolute;
        inset: 16px;
        border-radius: 50%;
        background: #11161f;
        box-shadow:
          inset 0 0 0 1px rgba(255,255,255,.06),
          0 0 0 1px rgba(0,0,0,.25);
      }

      #${CARD_ID} .ifssm-icon.small .ifssm-icon-hub {
        inset: 10px;
      }

      #${CARD_ID} .ifssm-icon.small .ifssm-icon-hole {
        inset: 15px;
      }

      @media (max-width: 640px) {
        #${CARD_ID} .ifssm-head {
          flex-direction: column;
          align-items: stretch;
        }

        #${CARD_ID} .ifssm-slots {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        #${CARD_ID} .ifssm-detail-top {
          flex-direction: column;
          align-items: stretch;
        }

        #${CARD_ID} .ifssm-badges {
          justify-content: flex-start;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function normalizeHex(value) {
    if (value == null) return null;
    const v = String(value).trim().replace(/^#/, "");
    if (!/^[0-9a-fA-F]{6}$/.test(v)) return null;
    return "#" + v.toUpperCase();
  }

  function splitStops(colors) {
    const count = colors.length;

    if (count === 2) {
      return [
        `${colors[0]} 0%`,
        `${colors[0]} 50%`,
        `${colors[1]} 50%`,
        `${colors[1]} 100%`
      ].join(", ");
    }

    const stops = [];

    colors.forEach((color, index) => {
      const start = (index * 100 / count).toFixed(4);
      const end = ((index + 1) * 100 / count).toFixed(4);

      stops.push(`${color} ${start}%`);
      stops.push(`${color} ${end}%`);
    });

    return stops.join(", ");
  }

  function getFilament(spool) {
    return spool && spool.filament ? spool.filament : {};
  }

  function getColors(spool) {
    const filament = getFilament(spool);
    const multi = String(filament.multi_color_hexes || "")
      .split(",")
      .map(normalizeHex)
      .filter(Boolean);

    if (multi.length) return multi;

    const single = normalizeHex(filament.color_hex);
    if (single) return [single];

    return ["#8E939B"];
  }

  function getDirection(spool) {
    const filament = getFilament(spool);
    return String(filament.multi_color_direction || "").trim().toLowerCase();
  }

  function getGradient(spool) {
    const colors = getColors(spool);
    const direction = getDirection(spool);

    if (colors.length <= 1) return colors[0];

    if (direction === "coaxial") {
      return `linear-gradient(90deg, ${splitStops(colors)})`;
    }

    if (direction === "longitudinal") {
      return `linear-gradient(135deg, ${splitStops(colors)})`;
    }

    return `linear-gradient(90deg, ${splitStops(colors)})`;
  }

  function getProgressGradient(spool) {
    const colors = getColors(spool);
    const direction = getDirection(spool);

    if (colors.length <= 1) return colors[0];

    if (direction === "coaxial") {
      return `linear-gradient(90deg, ${splitStops(colors)})`;
    }

    if (direction === "longitudinal") {
      return `linear-gradient(90deg, ${splitStops(colors)})`;
    }

    return `linear-gradient(90deg, ${splitStops(colors)})`;
  }

  function materialOf(spool) {
    const filament = getFilament(spool);
    return filament.material || "—";
  }

  function vendorOf(spool) {
    const filament = getFilament(spool);
    return (filament.vendor && filament.vendor.name) || "—";
  }

  function nameOf(spool) {
    const filament = getFilament(spool);
    return filament.name || "Без названия";
  }

  function spoolIdOf(spool) {
    return spool && spool.id != null ? spool.id : null;
  }

  function remainingWeight(spool) {
    return Number(spool && spool.remaining_weight || 0);
  }

  function initialWeight(spool) {
    return Number(spool && spool.initial_weight || 0);
  }

  function percentage(spool) {
    const total = initialWeight(spool);
    const remain = remainingWeight(spool);
    if (!total || total <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round(remain * 100 / total)));
  }

  function formatGram(value) {
    if (value == null || isNaN(value)) return "—";
    return `${Math.round(Number(value))} г`;
  }

  function weightLabel(spool) {
    return `${formatGram(remainingWeight(spool))} / ${formatGram(initialWeight(spool))}`;
  }

  function multiBadges(spool) {
    const colors = getColors(spool);
    const direction = getDirection(spool);

    if (colors.length < 2) return "";

    const map = {
      coaxial: "Коаксиальный",
      longitudinal: "Продольный"
    };

    const dirLabel = map[direction] || "Мультицвет";
    const countLabel = `${colors.length} цвета`;

    return `
      <span class="ifssm-badge accent">${dirLabel}</span>
      <span class="ifssm-badge accent">${countLabel}</span>
    `;
  }

  function renderIcon(spool, size = "small") {
    const bg = spool ? getGradient(spool) : "#8E939B";

    return `
      <div class="ifssm-icon ${size}">
        <div class="ifssm-icon-rim"></div>
        <div class="ifssm-icon-winding" style="background:${bg}"></div>
        <div class="ifssm-icon-hub"></div>
        <div class="ifssm-icon-hole"></div>
      </div>
    `;
  }

  function findAnchorCard() {
    const cards = Array.from(document.querySelectorAll(".v-card"));

    for (const card of cards) {
      const text = (card.innerText || "").toLowerCase();
      if (text.includes("spoolman") && !text.includes("ifs spoolman") && text.includes("сменить катушку")) {
        return card;
      }
    }

    for (const card of cards) {
      const text = (card.innerText || "").toLowerCase();
      if (text.includes("задания")) {
        return card.previousElementSibling || card;
      }
    }

    return cards.length ? cards[0] : null;
  }

  function ensureCard() {
    let el = document.getElementById(CARD_ID);
    if (el) return el;

    const anchor = findAnchorCard();
    if (!anchor || !anchor.parentElement) return null;

    el = document.createElement("div");
    el.id = CARD_ID;

    el.className = anchor.className;
    el.classList.add("ifssm-card");

    const anchorStyle = window.getComputedStyle(anchor);

    el.style.backgroundColor = anchorStyle.backgroundColor;
    el.style.backgroundImage = anchorStyle.backgroundImage;
    el.style.color = anchorStyle.color;
    el.style.borderColor = anchorStyle.borderColor;
    el.style.borderRadius = anchorStyle.borderRadius;
    el.style.boxShadow = anchorStyle.boxShadow;

    const headerCandidates = [
      anchor.querySelector(".v-toolbar"),
      anchor.querySelector(".v-card__title"),
      anchor.querySelector(".v-card-title"),
      anchor.querySelector("header"),
      anchor.firstElementChild
    ].filter(Boolean);

    const nativeHeader = headerCandidates.find(node => {
      const style = window.getComputedStyle(node);
      const height = node.getBoundingClientRect().height;

      return (
        height >= 32 &&
        height <= 70 &&
        style.backgroundColor !== "rgba(0, 0, 0, 0)"
      );
    }) || headerCandidates[0];

    if (nativeHeader) {
      const headerStyle = window.getComputedStyle(nativeHeader);

      el.style.setProperty(
        "--ifssm-header-background",
        headerStyle.backgroundImage !== "none"
          ? headerStyle.backgroundImage
          : headerStyle.backgroundColor
      );

      el.style.setProperty(
        "--ifssm-header-color",
        headerStyle.color
      );

      el.style.setProperty(
        "--ifssm-header-border",
        headerStyle.borderBottomColor
      );
    }

    anchor.insertAdjacentElement("afterend", el);
    return el;
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return await res.json();
  }

  async function refreshData() {
    try {
      const [status, spools] = await Promise.all([
        fetchJson(`${API_BASE}/api/status`),
        fetchJson(`${API_BASE}/api/spools`)
      ]);

      state.status = status || null;
      state.spools = Array.isArray(spools) ? spools : [];
      state.connected = !!(status && status.spoolman_connected);
      state.lastError = null;

      const activeSlot = Number(status && status.active_slot || 1);
      if (!state.selectedSlot) {
        state.selectedSlot = activeSlot || 1;
      }
    } catch (err) {
      state.connected = false;
      state.lastError = err && err.message ? err.message : String(err);
    }

    render();
  }

  function getAssignments() {
    const raw = (state.status && state.status.assignments) || {};
    const result = {};
    for (let i = 1; i <= 4; i++) {
      result[i] = raw[String(i)] == null ? null : Number(raw[String(i)]);
    }
    return result;
  }

  function spoolMap() {
    const map = new Map();
    for (const spool of state.spools) {
      map.set(Number(spool.id), spool);
    }
    return map;
  }

  function renderSlots(assignments, spoolsById, activeSlot) {
    let html = "";

    for (let slot = 1; slot <= 4; slot++) {
      const spoolId = assignments[slot];
      const spool = spoolId != null ? spoolsById.get(Number(spoolId)) : null;
      const selected = Number(state.selectedSlot) === slot;
      const classes = [
        "ifssm-slot",
        selected ? "is-selected" : "",
        spool ? "" : "unassigned"
      ].filter(Boolean).join(" ");

      html += `
        <div class="${classes}" data-slot="${slot}">
          <div class="ifssm-slot-top">
            <span class="ifssm-slot-num">${slot}</span>
          </div>
          <div class="ifssm-slot-body">
            ${renderIcon(spool, "small")}
            <div class="ifssm-slot-material">${spool ? materialOf(spool) : "—"}</div>
          </div>
        </div>
      `;
    }

    return html;
  }

  function renderDetail(slot, assignments, spoolsById, activeSlot) {
    const spoolId = assignments[slot];
    const spool = spoolId != null ? spoolsById.get(Number(spoolId)) : null;

    if (!spool) {
      return `
        <div class="ifssm-detail-top">
          <div>
            <div class="ifssm-name">IFS ${slot}</div>
            <div class="ifssm-meta">Катушка к этому слоту не назначена</div>
          </div>
          <div class="ifssm-badges">
            ${Number(activeSlot) === Number(slot) ? `<span class="ifssm-badge accent">Активный слот</span>` : ""}
          </div>
        </div>

        <div class="ifssm-row">
          ${renderIcon(null, "large")}
          <div class="ifssm-empty">
            Назначение отсутствует. Открой “Управление” и привяжи катушку Spoolman к этому слоту IFS.
          </div>
        </div>
      `;
    }

    const badges = [
      `<span class="ifssm-badge">${materialOf(spool)}</span>`,
      `<span class="ifssm-badge">ID ${spoolIdOf(spool)}</span>`,
      ...multiBadges(spool).trim() ? [multiBadges(spool)] : [],
      Number(activeSlot) === Number(slot) ? `<span class="ifssm-badge accent">Активный</span>` : ``
    ].filter(Boolean).join("");

    return `
      <div class="ifssm-detail-top">
        <div>
          <div class="ifssm-name">${escapeHtml(nameOf(spool))}</div>
          <div class="ifssm-meta">IFS ${slot} · ${escapeHtml(vendorOf(spool))}</div>
        </div>
        <div class="ifssm-badges">${badges}</div>
      </div>

      <div class="ifssm-row">
        ${renderIcon(spool, "large")}
        <div>
          <div class="ifssm-progress-label">
            <span>Остаток</span>
            <span class="ifssm-progress-value">${weightLabel(spool)} · ${percentage(spool)}%</span>
          </div>
          <div class="ifssm-progress">
            <span style="width:${percentage(spool)}%; background:${getProgressGradient(spool)}"></span>
          </div>
        </div>
      </div>
    `;
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render() {
    injectStyles();

    const el = ensureCard();
    if (!el) return;

    const assignments = getAssignments();
    const spoolsById = spoolMap();
    const activeSlot = Number(state.status && state.status.active_slot || 1);

    if (!state.selectedSlot) state.selectedSlot = activeSlot || 1;
    if (state.selectedSlot < 1 || state.selectedSlot > 4) state.selectedSlot = activeSlot || 1;

    const assignedCount = Object.values(assignments).filter(v => v != null).length;
    const currentSpoolId = state.status && state.status.moonraker_spool_id != null
      ? Number(state.status.moonraker_spool_id)
      : null;
    const currentSpool = currentSpoolId != null ? spoolsById.get(currentSpoolId) : null;
    const currentLabel = currentSpool ? `${vendorOf(currentSpool)} · ${nameOf(currentSpool)}` : "—";

    el.innerHTML = `
      <div class="ifssm-wrap">
        <div class="ifssm-head">
          <div class="ifssm-head-left">
            <span
              class="ifssm-brand-icon"
              aria-hidden="true"
              title="AD5X IFS Plugin for Spoolman"
            >
              <svg
                viewBox="0 0 24 24"
                role="img"
                focusable="false"
              >
                <circle
                  class="ifs-icon-line"
                  cx="8.2"
                  cy="10.2"
                  r="6.1"
                />

                <circle
                  class="ifs-icon-line"
                  cx="8.2"
                  cy="10.2"
                  r="2.05"
                />

                <circle class="ifs-icon-fill" cx="8.2" cy="5.45" r=".72"/>
                <circle class="ifs-icon-fill" cx="11.55" cy="6.85" r=".72"/>
                <circle class="ifs-icon-fill" cx="12.95" cy="10.2" r=".72"/>
                <circle class="ifs-icon-fill" cx="11.55" cy="13.55" r=".72"/>
                <circle class="ifs-icon-fill" cx="8.2" cy="14.95" r=".72"/>
                <circle class="ifs-icon-fill" cx="4.85" cy="13.55" r=".72"/>
                <circle class="ifs-icon-fill" cx="3.45" cy="10.2" r=".72"/>
                <circle class="ifs-icon-fill" cx="4.85" cy="6.85" r=".72"/>

                <path
                  class="ifs-icon-line"
                  d="M8.2 16.3v2.1h8.1"
                />

                <path
                  class="ifs-icon-line"
                  d="M16.3 18.4h3.25"
                />

                <path
                  class="ifs-icon-line"
                  d="M17.35 15.55v5.7"
                />

                <path
                  class="ifs-icon-line"
                  d="M17.35 15.55h2.15"
                />

                <path
                  class="ifs-icon-line"
                  d="M17.35 18.4h1.75"
                />

                <path
                  class="ifs-icon-line"
                  d="M17.35 21.25h2.15"
                />
              </svg>
            </span>

            <div>
              <div class="ifssm-title">AD5X IFS</div>
              <div class="ifssm-sub">Plugin for Spoolman</div>
            </div>
            <div class="ifssm-status ${state.connected ? "connected" : ""}">
              ${state.connected ? "Подключено" : "Нет связи"}
            </div>
          </div>
          <button class="ifssm-manage" type="button">УПРАВЛЕНИЕ</button>
        </div>

        <div class="ifssm-slots">
          ${renderSlots(assignments, spoolsById, activeSlot)}
        </div>

        <div class="ifssm-detail">
          ${renderDetail(Number(state.selectedSlot), assignments, spoolsById, activeSlot)}
          <div class="ifssm-footer">
            Активный слот: IFS ${activeSlot} · Текущая катушка Moonraker: ${escapeHtml(currentLabel)} · Назначено: ${assignedCount}/4
            ${state.lastError ? ` · Ошибка: ${escapeHtml(state.lastError)}` : ""}
          </div>
        </div>
      </div>
    `;

    const manageBtn = el.querySelector(".ifssm-manage");
    if (manageBtn) {
      manageBtn.addEventListener("click", () => {
        window.open(MANAGE_URL, "_blank");
      });
    }

    el.querySelectorAll(".ifssm-slot[data-slot]").forEach(node => {
      node.addEventListener("click", () => {
        state.selectedSlot = Number(node.getAttribute("data-slot"));
        render();
      });
    });
  }

  function start() {
    injectStyles();
    render();
    refreshData();

    setInterval(refreshData, 15000);

    const observer = new MutationObserver(() => {
      if (!document.getElementById(CARD_ID)) {
        render();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
