(() => {
  "use strict";

  const VERSION = "1.0.0";
  const CARD_ID = "ifs-spoolman-fluidd-card";
  const STYLE_ID = "ifs-spoolman-selection-style";
  const API_BASE = `${location.protocol}//${location.hostname}:7913`;

  let activeSlot = null;
  let observer = null;
  let refreshTimer = null;
  let scheduled = false;

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CARD_ID} .ifssm-slot.is-selected {
        border-color: rgba(66, 153, 225, .92) !important;
        background: rgba(66, 153, 225, .10) !important;
        box-shadow: inset 0 0 0 1px rgba(66, 153, 225, .22) !important;
      }

      #${CARD_ID} .ifssm-slot.is-selected .ifssm-slot-num {
        background: rgba(66, 153, 225, .22) !important;
        color: #a9d5ff !important;
      }

      #${CARD_ID} .ifssm-slot.is-active-slot {
        border-color: rgba(40, 185, 92, .92) !important;
        background: rgba(40, 185, 92, .11) !important;
        box-shadow:
          inset 0 0 0 1px rgba(40, 185, 92, .22),
          0 0 0 1px rgba(40, 185, 92, .08) !important;
      }

      #${CARD_ID} .ifssm-slot.is-active-slot .ifssm-slot-num {
        background: rgba(40, 185, 92, .24) !important;
        color: #7ef1ab !important;
      }

      #${CARD_ID} .ifssm-slot.is-active-slot.is-selected {
        border-color: rgba(40, 185, 92, .98) !important;
        background:
          linear-gradient(135deg, rgba(40, 185, 92, .13), rgba(66, 153, 225, .08)) !important;
        box-shadow:
          inset 0 0 0 1px rgba(40, 185, 92, .25),
          inset 0 -3px 0 rgba(66, 153, 225, .72) !important;
      }

      #${CARD_ID} .ifssm-slot-active-marker {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        min-height: 17px;
        padding: 0 6px;
        border-radius: 999px;
        background: rgba(40, 185, 92, .18);
        color: #7ef1ab;
        font-size: 8px;
        font-weight: 800;
        letter-spacing: .02em;
        line-height: 1;
        white-space: nowrap;
      }

      #${CARD_ID} .ifssm-slot-active-marker::before {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #2ecc71;
        box-shadow: 0 0 0 2px rgba(46, 204, 113, .16);
        content: "";
      }
    `;
    document.head.appendChild(style);
  }

  function applyState() {
    scheduled = false;
    const card = document.getElementById(CARD_ID);
    if (!card) return;

    card.querySelectorAll(".ifssm-slot[data-slot]").forEach(slot => {
      const slotNumber = Number(slot.getAttribute("data-slot"));
      const isActive = activeSlot !== null && slotNumber === activeSlot;
      slot.classList.toggle("is-active-slot", isActive);

      const top = slot.querySelector(".ifssm-slot-top");
      let marker = slot.querySelector(".ifssm-slot-active-marker");

      if (isActive && top) {
        if (!marker) {
          marker = document.createElement("span");
          marker.className = "ifssm-slot-active-marker";
          marker.textContent = "АКТИВНА";
          top.appendChild(marker);
        }
      } else if (marker) {
        marker.remove();
      }
    });
  }

  function scheduleApply() {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(applyState, 50);
  }

  async function refreshActiveSlot() {
    try {
      const response = await fetch(`${API_BASE}/api/status`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const status = await response.json();
      const value = Number(status && status.active_slot);
      activeSlot = Number.isInteger(value) && value >= 1 && value <= 4 ? value : null;
    } catch {
      activeSlot = null;
    }
    scheduleApply();
  }

  function start() {
    installStyles();
    refreshActiveSlot();

    observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, { childList: true, subtree: true });

    refreshTimer = window.setInterval(refreshActiveSlot, 3000);

    window.addEventListener("beforeunload", () => {
      if (observer) observer.disconnect();
      if (refreshTimer !== null) clearInterval(refreshTimer);
    });

    console.info(`IFS Spoolman active/selected slot styling v${VERSION} loaded`);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
