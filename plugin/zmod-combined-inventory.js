(() => {
  "use strict";

  const REFRESH_MS = 30000;
  let timer = null;
  let running = false;
  let latestPayload = null;
  let spoolCache = null;

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

  function parseColors(single, multiple) {
    const colors = String(multiple || "")
      .split(",")
      .map(normalizeHex)
      .filter(Boolean);
    if (colors.length) return colors;
    const fallback = normalizeHex(single);
    return fallback ? [fallback] : ["#64748B"];
  }

  function hardStops(colors, unit = "%") {
    const size = (unit === "deg" ? 360 : 100) / colors.length;
    return colors.flatMap((color, index) => {
      const start = (size * index).toFixed(2);
      const end = (size * (index + 1)).toFixed(2);
      return [`${color} ${start}${unit}`, `${color} ${end}${unit}`];
    }).join(", ");
  }

  function smoothGradient(colors) {
    if (colors.length <= 1) return colors[0];
    return `linear-gradient(90deg, ${colors.join(", ")})`;
  }

  function colorVisual(single, multiple, direction) {
    const colors = parseColors(single, multiple);
    const mode = String(direction || "").toLowerCase();
    const sequential = ["linear", "gradient", "rainbow", "sequential", "alternating", "random", "change"]
      .some(item => mode === item || mode.includes(item));

    if (colors.length === 1) {
      return { colors, swatch: colors[0], progress: colors[0], count: 1, sequential: false };
    }

    const discrete = !sequential && colors.length <= 4;
    const swatch = discrete
      ? `conic-gradient(from -90deg, ${hardStops(colors, "deg")})`
      : `conic-gradient(from -90deg, ${[...colors, colors[0]].join(", ")})`;
    const progress = discrete
      ? `linear-gradient(90deg, ${hardStops(colors)})`
      : smoothGradient(colors);

    return { colors, swatch, progress, count: colors.length, sequential };
  }

  function colorCountText(count) {
    if (count % 10 === 1 && count % 100 !== 11) return `${count} цвет`;
    if ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) return `${count} цвета`;
    return `${count} цветов`;
  }

  function ensureStyles() {
    if (document.getElementById("combined-inventory-styles")) return;
    const style = document.createElement("style");
    style.id = "combined-inventory-styles";
    style.textContent = `
      .slot-head{align-items:flex-start;min-height:42px;margin-bottom:7px}.slot-head>div:last-child{min-width:0;padding-top:1px}.presence{line-height:1.2}.empty-note{display:block!important;margin:2px 0 0!important;font-size:9px!important;line-height:1.15;color:#aeb8cc}.actions{gap:5px}.actions button{min-width:0;padding-left:9px;padding-right:9px}.palette-line{min-height:25px}.palette-toggle{align-self:center;white-space:nowrap}
      .combined-inventory{margin-top:7px;padding-top:7px;border-top:1px solid rgba(148,163,184,.14)}.combined-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:5px;color:#9eabc4;font-size:9px;font-weight:800;letter-spacing:.05em;text-transform:uppercase}.combined-title-actions{display:flex;align-items:center;gap:5px}.combined-badge{padding:2px 6px;border:1px solid rgba(91,140,255,.28);border-radius:999px;background:rgba(91,140,255,.09);color:#8fb0ff;font-size:8px;letter-spacing:0;text-transform:none}.combined-change{height:21px;padding:0 7px;border-radius:7px;font-size:8px;letter-spacing:0;text-transform:none;background:rgba(91,140,255,.10);border-color:rgba(91,140,255,.28);color:#b7c9ff}
      .combined-card{display:grid;grid-template-columns:36px minmax(0,1fr);gap:9px;padding:7px 8px;border:1px solid rgba(148,163,184,.16);border-radius:9px;background:rgba(26,35,56,.62)}.combined-swatch{--spool-visual:#64748b;position:relative;width:36px;height:36px;border:1px solid rgba(255,255,255,.11);border-radius:50%;background:rgba(7,12,24,.9);box-shadow:0 0 0 2px rgba(255,255,255,.028),inset 0 0 0 1px rgba(0,0,0,.25)}.combined-swatch::before{content:"";position:absolute;inset:2px;border-radius:50%;background:var(--spool-visual);box-shadow:inset 0 0 0 1px rgba(0,0,0,.22)}.combined-swatch::after{content:"";position:absolute;left:50%;top:50%;width:7px;height:7px;transform:translate(-50%,-50%);border:1px solid rgba(255,255,255,.20);border-radius:50%;background:#101728;box-shadow:0 0 0 1px rgba(0,0,0,.30)}.combined-main{min-width:0}.combined-topline{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:baseline;gap:7px;min-width:0}.combined-name{min-width:0;font-size:11px;font-weight:800;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.combined-vendor{max-width:105px;color:#9eabc4;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.combined-detail{display:flex;align-items:center;gap:7px;min-width:0;margin-top:3px}.combined-meta{display:flex;align-items:center;gap:4px;flex:0 0 auto}.combined-pill{padding:1px 5px;border:1px solid rgba(148,163,184,.16);border-radius:999px;color:#b9c4d9;font-size:8px}.combined-color-count{color:#b9a8ff;font-size:8px;font-weight:750;white-space:nowrap}.combined-weight{min-width:0;color:#cdd6e7;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.combined-progress{position:relative;height:4px;margin-top:5px;overflow:hidden;border:1px solid rgba(148,163,184,.10);border-radius:999px;background:rgba(148,163,184,.13)}.combined-progress>span{display:block;height:100%;border-radius:inherit;background:#5b8cff}.combined-empty,.combined-offline{padding:7px 8px;border:1px dashed rgba(148,163,184,.20);border-radius:9px;color:#9eabc4;font-size:9px;line-height:1.35}.combined-warning{margin-top:4px;color:rgba(245,196,81,.82);font-size:8px;font-weight:650;line-height:1.2;white-space:normal}
      .assign-overlay{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:18px;background:rgba(2,6,23,.72);backdrop-filter:blur(5px)}.assign-dialog{width:min(650px,100%);max-height:min(760px,calc(100vh - 36px));display:flex;flex-direction:column;overflow:hidden;border:1px solid rgba(148,163,184,.24);border-radius:16px;background:#141b2d;box-shadow:0 28px 80px rgba(0,0,0,.48)}.assign-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:15px 16px 12px;border-bottom:1px solid rgba(148,163,184,.16)}.assign-title{font-size:16px;font-weight:850}.assign-sub{margin-top:3px;color:#9eabc4;font-size:11px}.assign-close{width:32px;height:32px;padding:0;border-radius:9px;font-size:18px}.assign-search{margin:12px 16px 8px}.assign-search input{height:38px}.assign-list{display:grid;gap:7px;min-height:120px;overflow:auto;padding:4px 16px 12px}.assign-option{display:grid;grid-template-columns:22px 34px minmax(0,1fr) auto;align-items:center;gap:9px;padding:9px 10px;border:1px solid rgba(148,163,184,.16);border-radius:11px;background:rgba(26,35,56,.58);cursor:pointer}.assign-option:hover{border-color:rgba(91,140,255,.42)}.assign-option.selected{border-color:#5b8cff;box-shadow:0 0 0 2px rgba(91,140,255,.12)}.assign-radio{width:15px;height:15px}.assign-swatch{--spool-visual:#64748b;position:relative;width:30px;height:30px;border:1px solid rgba(255,255,255,.11);border-radius:50%;background:rgba(7,12,24,.9)}.assign-swatch::before{content:"";position:absolute;inset:2px;border-radius:50%;background:var(--spool-visual)}.assign-swatch::after{content:"";position:absolute;left:50%;top:50%;width:6px;height:6px;transform:translate(-50%,-50%);border:1px solid rgba(255,255,255,.20);border-radius:50%;background:#101728}.assign-main{min-width:0}.assign-name{font-size:12px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.assign-meta{margin-top:2px;color:#9eabc4;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.assign-weight{color:#cdd6e7;font-size:10px;white-space:nowrap}.assign-empty{padding:18px;color:#9eabc4;text-align:center;font-size:11px}.assign-status{min-height:18px;padding:0 16px 8px;color:#ffb4bd;font-size:10px}.assign-footer{display:flex;justify-content:flex-end;gap:8px;padding:12px 16px;border-top:1px solid rgba(148,163,184,.16)}.assign-footer button{height:36px}.assign-footer .primary{min-width:100px}body.assign-open{overflow:hidden}
      @media(max-width:760px){.combined-card{grid-template-columns:32px minmax(0,1fr)}.combined-swatch{width:32px;height:32px}.combined-detail{flex-wrap:wrap}.combined-vendor{max-width:90px}.assign-option{grid-template-columns:20px 30px minmax(0,1fr)}.assign-weight{grid-column:3}.assign-dialog{max-height:calc(100vh - 20px)}}
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
    const canAssign = provider === "spoolman" && slotData.inventory_available;
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
      const visual = colorVisual(inventory.color_hex, inventory.multi_color_hexes, inventory.multi_color_direction);
      const tooltip = visual.colors.join(", ");
      const colorCount = visual.count > 1
        ? `<span class="combined-color-count" title="${esc(tooltip)}">${esc(colorCountText(visual.count))}</span>`
        : "";
      const warning = slotData.mismatch
        ? `<div class="combined-warning">Цвет или материал слота не совпадает с учётной катушкой</div>`
        : "";

      body = `<div class="combined-card"><div class="combined-swatch" title="${esc(tooltip)}" style="--spool-visual:${esc(visual.swatch)}"></div><div class="combined-main"><div class="combined-topline"><div class="combined-name" title="${esc(inventory.name || `Катушка #${inventory.spool_id}`)}">${esc(inventory.name || `Катушка #${inventory.spool_id}`)}</div><div class="combined-vendor" title="${esc(inventory.vendor || "Без производителя")}">${esc(inventory.vendor || "Без производителя")}</div></div><div class="combined-detail"><div class="combined-meta"><span class="combined-pill">ID ${esc(inventory.spool_id)}</span><span class="combined-pill">${esc(inventory.material || "Материал не указан")}</span>${colorCount}</div><div class="combined-weight">Остаток: ${formatWeight(remaining)} / ${formatWeight(initial)}${percent === null ? "" : ` · ${Math.round(percent)}%`}</div></div>${percent === null ? "" : `<div class="combined-progress" title="Остаток ${Math.round(percent)}%"><span style="width:${percent.toFixed(1)}%;background:${esc(visual.progress)}"></span></div>`}${warning}</div></div>`;
    }

    section.innerHTML = `<div class="combined-title"><span>Учётная катушка</span><span class="combined-title-actions"><span class="combined-badge">${esc(titleBadge)}</span>${canAssign ? `<button type="button" class="combined-change" data-assign-slot="${slot}">Сменить</button>` : ""}</span></div>${body}`;
    host.appendChild(section);
  }

  function spoolInfo(spool) {
    const filament = spool?.filament || {};
    const visual = colorVisual(filament.color_hex, filament.multi_color_hexes, filament.multi_color_direction);
    return {
      id: Number(spool?.id),
      name: filament.name || `Катушка #${spool?.id}`,
      vendor: filament.vendor?.name || "Без производителя",
      material: filament.material || "Материал не указан",
      visual,
      remaining: spool?.remaining_weight
    };
  }

  function usedByOtherSlot(spoolId, slot) {
    return Object.values(latestPayload?.slots || {}).some(item => Number(item.slot) !== slot && Number(item.inventory?.spool_id) === Number(spoolId));
  }

  async function loadSpools() {
    if (Array.isArray(spoolCache)) return spoolCache;
    const response = await fetch("/api/spools", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    spoolCache = Array.isArray(payload) ? payload : [];
    return spoolCache;
  }

  function closeDialog() {
    document.querySelector(".assign-overlay")?.remove();
    document.body.classList.remove("assign-open");
  }

  async function openDialog(slot) {
    closeDialog();
    const slotData = latestPayload?.slots?.[String(slot)];
    if (!slotData) return;
    const currentId = slotData.inventory?.spool_id ?? null;
    const overlay = document.createElement("div");
    overlay.className = "assign-overlay";
    overlay.innerHTML = `<section class="assign-dialog" role="dialog" aria-modal="true" aria-label="Назначение катушки"><header class="assign-head"><div><div class="assign-title">Катушка Spoolman для IFS ${slot}</div><div class="assign-sub">Выбор меняет только учётное назначение. Команды IFS не выполняются.</div></div><button type="button" class="assign-close" aria-label="Закрыть">×</button></header><div class="assign-search"><input type="text" placeholder="Поиск по ID, производителю, названию или материалу"></div><div class="assign-list"><div class="assign-empty">Загрузка катушек…</div></div><div class="assign-status"></div><footer class="assign-footer"><button type="button" class="assign-cancel">Отмена</button><button type="button" class="primary assign-save">Сохранить</button></footer></section>`;
    document.body.appendChild(overlay);
    document.body.classList.add("assign-open");
    overlay.addEventListener("click", event => { if (event.target === overlay) closeDialog(); });
    overlay.querySelector(".assign-close").addEventListener("click", closeDialog);
    overlay.querySelector(".assign-cancel").addEventListener("click", closeDialog);
    document.addEventListener("keydown", function onKey(event) {
      if (event.key === "Escape") { document.removeEventListener("keydown", onKey); closeDialog(); }
    });

    let selected = currentId === null ? "" : String(currentId);
    const input = overlay.querySelector(".assign-search input");
    const list = overlay.querySelector(".assign-list");
    const status = overlay.querySelector(".assign-status");
    const save = overlay.querySelector(".assign-save");

    try {
      const spools = await loadSpools();
      const render = () => {
        const query = input.value.trim().toLowerCase();
        const available = spools.filter(spool => {
          const info = spoolInfo(spool);
          if (spool.archived || usedByOtherSlot(info.id, slot)) return false;
          const haystack = `${info.id} ${info.vendor} ${info.name} ${info.material}`.toLowerCase();
          return !query || haystack.includes(query);
        });
        const options = [{ id: "", name: "Не назначено", vendor: "Снять привязку Spoolman", material: "", visual: { swatch: "#475569", count: 1, colors: ["#475569"] }, remaining: null }, ...available.map(spoolInfo)];
        list.innerHTML = options.map(item => `<label class="assign-option${String(item.id) === selected ? " selected" : ""}"><input class="assign-radio" type="radio" name="assign-spool" value="${esc(item.id)}"${String(item.id) === selected ? " checked" : ""}><span class="assign-swatch" title="${esc(item.visual.colors.join(", "))}" style="--spool-visual:${esc(item.visual.swatch)}"></span><span class="assign-main"><span class="assign-name" title="${esc(item.name)}">${esc(item.name)}</span><span class="assign-meta">${esc(item.vendor)}${item.material ? ` · ${esc(item.material)} · ID ${esc(item.id)}${item.visual.count > 1 ? ` · ${esc(colorCountText(item.visual.count))}` : ""}` : ""}</span></span><span class="assign-weight">${item.id === "" ? "" : formatWeight(item.remaining)}</span></label>`).join("") || `<div class="assign-empty">Подходящих катушек не найдено.</div>`;
        list.querySelectorAll("input[name=assign-spool]").forEach(radio => radio.addEventListener("change", event => { selected = event.currentTarget.value; render(); }));
      };
      input.addEventListener("input", render);
      render();
      input.focus();
    } catch (error) {
      list.innerHTML = `<div class="assign-empty">Не удалось загрузить катушки Spoolman.</div>`;
      status.textContent = error instanceof Error ? error.message : String(error);
      save.disabled = true;
    }

    save.addEventListener("click", async () => {
      const spoolId = selected === "" ? null : Number(selected);
      const activeSlot = Number(latestPayload?.local?.active_slot);
      if (slot === activeSlot && spoolId === null && currentId !== null) {
        const ok = window.confirm(`Активный слот IFS ${slot} останется без катушки Spoolman. Продолжить?`);
        if (!ok) return;
      }
      save.disabled = true;
      status.textContent = "Сохранение…";
      try {
        const response = await fetch("/api/assign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slot, spool_id: spoolId }) });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        spoolCache = null;
        closeDialog();
        await refresh(true);
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : String(error);
        save.disabled = false;
      }
    });
  }

  async function refresh(force = false) {
    if (running || (!force && document.hidden)) return;
    running = true;
    try {
      const response = await fetch("/api/inventory/combined", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      latestPayload = payload;
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
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-assign-slot]");
    if (button) openDialog(Number(button.dataset.assignSlot));
  });
  window.setTimeout(refresh, 800);
  schedule();
  document.addEventListener("visibilitychange", () => { if (!document.hidden) window.setTimeout(refresh, 300); });
  window.addEventListener("beforeunload", () => clearInterval(timer));
})();
