(() => {
  "use strict";

  const REFRESH_MS = 30000;
  let timer = null;
  let running = false;

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[char]));
  }

  function formatWeight(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    if (number >= 1000) {
      const kg = number / 1000;
      return `${kg % 1 === 0 ? kg.toFixed(0) : kg.toFixed(2)} кг`;
    }
    return `${Math.round(number)} г`;
  }

  function normalizeHex(value) {
    const raw = String(value || "").trim().replace(/^#/, "");
    return /^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(raw)
      ? `#${raw.slice(0, 6).toUpperCase()}`
      : null;
  }

  function ensureStyles() {
    if (document.getElementById("combined-inventory-styles")) return;
    const style = document.createElement("style");
    style.id = "combined-inventory-styles";
    style.textContent = `
      .slot-head{align-items:flex-start;min-height:42px;margin-bottom:7px}
      .slot-head>div:last-child{min-width:0;padding-top:1px}
      .presence{line-height:1.2}
      .empty-note{display:block!important;margin:2px 0 0!important;font-size:9px!important;line-height:1.15;color:#aeb8cc}
      .actions{gap:5px}
      .actions button{min-width:0;padding-left:9px;padding-right:9px}
      .palette-line{min-height:25px}
      .palette-toggle{align-self:center;white-space:nowrap}

      .combined-inventory{margin-top:7px;padding-top:7px;border-top:1px solid rgba(148,163,184,.14)}
      .combined-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:5px;color:#9eabc4;font-size:9px;font-weight:800;letter-spacing:.05em;text-transform:uppercase}
      .combined-badge{padding:2px 6px;border:1px solid rgba(91,140,255,.28);border-radius:999px;background:rgba(91,140,255,.09);color:#8fb0ff;font-size:8px;letter-spacing:0;text-transform:none}
      .combined-card{display:grid;grid-template-columns:34px minmax(0,1fr);gap:8px;padding:7px 8px;border:1px solid rgba(148,163,184,.16);border-radius:9px;background:rgba(26,35,56,.62)}
      .combined-swatch{width:34px;height:34px;border:4px solid rgba(255,255,255,.14);border-radius:50%;background:#64748b;box-shadow:inset 0 0 0 2px rgba(0,0,0,.25)}
      .combined-main{min-width:0}
      .combined-topline{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:baseline;gap:7px;min-width:0}
      .combined-name{min-width:0;font-size:11px;font-weight:800;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .combined-vendor{max-width:105px;color:#9eabc4;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .combined-detail{display:flex;align-items:center;gap:6px;min-width:0;margin-top:3px}
      .combined-meta{display:flex;gap:4px;flex:0 0 auto}
      .combined-pill{padding:1px 5px;border:1px solid rgba(148,163,184,.16);border-radius:999px;color:#b9c4d9;font-size:8px}
      .combined-weight{min-width:0;color:#cdd6e7;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .combined-progress{height:3px;margin-top:4px;overflow:hidden;border-radius:999px;background:rgba(148,163,184,.16)}
      .combined-progress>span{display:block;height:100%;border-radius:inherit;background:#5b8cff}
      .combined-empty,.combined-offline{padding:7px 8px;border:1px dashed rgba(148,163,184,.20);border-radius:9px;color:#9eabc4;font-size:9px;line-height:1.35}
      .combined-warning{margin-top:4px;color:#f5c451;font-size:9px;font-weight:750;line-height:1.2;white-space:normal}
      @media(max-width:760px){
        .combined-card{grid-template-columns:30px minmax(0,1fr)}
        .combined-swatch{width:30px;height:30px}
        .combined-detail{flex-wrap:wrap}
        .combined-vendor{max-width:90px}
      }
    `;
    document.head.appendChild(style);
  }

  function renderSlot(slotData) {
    const slot = Number(slotData.slot);
    const host = document.querySelector(`.slot[data-slot="${slot}"]`);
    if (!host) return;

    host.querySelector(".combined-inventory")?.remove();
    const section = document.createElement("section");
    section.className = "combined-inventory";

    const inventory = slotData.inventory || {};
    const provider = slotData.provider || "local";
    const titleBadge = provider === "spoolman" ? "Spoolman" : "Локально";

    let body = "";
    if (provider !== "spoolman") {
      body = `<div class="combined-empty">Автономный режим: используются данные Z-Mod и физическое состояние IFS.</div>`;
    } else if (!slotData.inventory_available) {
      body = `<div class="combined-offline">Spoolman временно недоступен. Локальные данные слота продолжают работать автономно.</div>`;
    } else if (!inventory.assigned) {
      body = `<div class="combined-empty">Катушка Spoolman этому слоту не назначена.</div>`;
    } else {
      const remaining = Number(inventory.remaining_weight);
      const initial = Number(inventory.initial_weight);
      const percent = Number.isFinite(remaining) && Number.isFinite(initial) && initial > 0
        ? Math.max(0, Math.min(100, remaining / initial * 100))
        : null;
      const color = normalizeHex(inventory.color_hex) || "#64748B";
      body = `
        <div class="combined-card">
          <div class="combined-swatch" style="background:${esc(color)}"></div>
          <div class="combined-main">
            <div class="combined-topline"><div class="combined-name" title="${esc(inventory.name || `Катушка #${inventory.spool_id}`)}">${esc(inventory.name || `Катушка #${inventory.spool_id}`)}</div><div class="combined-vendor" title="${esc(inventory.vendor || "Без производителя")}">${esc(inventory.vendor || "Без производителя")}</div></div>
            <div class="combined-detail"><div class="combined-meta"><span class="combined-pill">ID ${esc(inventory.spool_id)}</span><span class="combined-pill">${esc(inventory.material || "Материал не указан")}</span></div><div class="combined-weight">Остаток: ${formatWeight(remaining)} / ${formatWeight(initial)}${percent === null ? "" : ` · ${Math.round(percent)}%`}</div></div>
            ${percent === null ? "" : `<div class="combined-progress"><span style="width:${percent.toFixed(1)}%"></span></div>`}
            ${slotData.mismatch ? `<div class="combined-warning">Локальные параметры слота отличаются от данных Spoolman</div>` : ""}
          </div>
        </div>`;
    }

    section.innerHTML = `
      <div class="combined-title"><span>Учётная катушка</span><span class="combined-badge">${esc(titleBadge)}</span></div>
      ${body}
    `;
    host.appendChild(section);
  }

  async function refresh() {
    if (running || document.hidden) return;
    running = true;
    try {
      const response = await fetch("/api/inventory/combined", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      Object.values(payload.slots || {}).forEach(renderSlot);
    } catch (_) {
      // Existing local editor remains fully usable.
    } finally {
      running = false;
    }
  }

  function schedule() {
    clearInterval(timer);
    timer = setInterval(refresh, REFRESH_MS);
  }

  ensureStyles();
  window.setTimeout(refresh, 800);
  schedule();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) window.setTimeout(refresh, 300);
  });
  window.addEventListener("beforeunload", () => clearInterval(timer));
})();
