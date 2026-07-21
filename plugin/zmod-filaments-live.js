(() => {
  "use strict";

  const IDLE_POLL_MS = 30000;
  const ACTIVITY_POLL_MS = 3000;
  const EVENT_REFRESH_DELAY_MS = 2500;
  const DIRTY_CLASS = "ifs-editor-dirty";
  const PRINTING_STATES = new Set(["printing", "paused"]);

  let stopped = false;
  let requestRunning = false;
  let eventRefreshRunning = false;
  let dirty = false;
  let lastSignature = null;
  let lastPrintState = null;
  let lastActiveSlot = null;
  let timer = null;
  let eventTimer = null;

  function api(path) {
    return fetch(path, { cache: "no-store" }).then(async response => {
      let payload = {};
      try {
        payload = await response.json();
      } catch (_) {
        // Empty payload is handled as an unavailable state by the caller.
      }
      if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      return payload;
    });
  }

  function presenceValue(presence, slot) {
    return presence && presence.slots && presence.slots[String(slot)]
      ? presence.slots[String(slot)].filament_present
      : null;
  }

  function signature(metadata, presence) {
    const slots = [];
    for (let slot = 1; slot <= 4; slot += 1) {
      const meta = metadata && metadata.slots
        ? metadata.slots[String(slot)] || {}
        : {};
      slots.push({
        slot,
        color: meta.color || null,
        material: meta.material || null,
        present: presenceValue(presence, slot)
      });
    }
    return JSON.stringify({
      activeSlot: Number(metadata && metadata.active_slot || 0),
      available: !!(presence && presence.available),
      stale: !!(presence && presence.stale),
      slots
    });
  }

  function setDirty(value) {
    dirty = !!value;
    document.documentElement.classList.toggle(DIRTY_CLASS, dirty);
  }

  function watchEditorChanges() {
    document.addEventListener("input", event => {
      if (event.target.closest(".slot")) {
        setDirty(true);
      }
    }, true);

    document.addEventListener("change", event => {
      if (event.target.closest(".slot")) {
        setDirty(true);
      }
    }, true);

    document.addEventListener("click", event => {
      const reset = event.target.closest("button.reset");
      if (reset) {
        window.setTimeout(() => setDirty(false), 0);
        return;
      }
      const save = event.target.closest("button.save");
      if (save) {
        window.setTimeout(() => setDirty(false), 1500);
      }
    }, true);
  }

  async function refreshAfterPrintEvent() {
    if (stopped || eventRefreshRunning || document.hidden) {
      return;
    }
    eventRefreshRunning = true;
    try {
      await api("/api/ifs/slots?refresh=1");
      if (!dirty) {
        location.reload();
      }
    } catch (_) {
      // Keep the current page; a later activity event or idle cycle retries.
    } finally {
      eventRefreshRunning = false;
    }
  }

  function queueEventRefresh() {
    window.clearTimeout(eventTimer);
    eventTimer = window.setTimeout(refreshAfterPrintEvent, EVENT_REFRESH_DELAY_MS);
  }

  async function pollPrinting(activity) {
    const printState = String(activity.print_state || "unknown").toLowerCase();
    const activeSlot = Number(activity.active_slot || 0);

    if (lastPrintState === null) {
      lastPrintState = printState;
      lastActiveSlot = activeSlot;
      return;
    }

    const wasPrinting = PRINTING_STATES.has(lastPrintState);
    const isPrinting = PRINTING_STATES.has(printState);
    const printTransition = wasPrinting !== isPrinting;
    const slotChanged = activeSlot > 0 && lastActiveSlot > 0 && activeSlot !== lastActiveSlot;

    lastPrintState = printState;
    lastActiveSlot = activeSlot;

    if (printTransition || (isPrinting && slotChanged)) {
      queueEventRefresh();
    }
  }

  async function pollIdle() {
    const [metadata, presence] = await Promise.all([
      api("/api/zmod/filaments"),
      api("/api/ifs/slots")
    ]);
    const currentSignature = signature(metadata, presence);

    if (lastSignature === null) {
      lastSignature = currentSignature;
    } else if (currentSignature !== lastSignature) {
      lastSignature = currentSignature;
      if (!dirty) {
        location.reload();
      }
    }
  }

  async function poll() {
    if (stopped || requestRunning || document.hidden) {
      schedule(ACTIVITY_POLL_MS);
      return;
    }

    requestRunning = true;
    let nextDelay = IDLE_POLL_MS;
    try {
      const activity = await api("/api/printer/activity");
      const printState = String(activity.print_state || "unknown").toLowerCase();
      const isPrinting = PRINTING_STATES.has(printState);
      await pollPrinting(activity);

      if (isPrinting) {
        nextDelay = ACTIVITY_POLL_MS;
      } else {
        await pollIdle();
        nextDelay = IDLE_POLL_MS;
      }
    } catch (_) {
      nextDelay = ACTIVITY_POLL_MS;
    } finally {
      requestRunning = false;
      schedule(nextDelay);
    }
  }

  function schedule(delay) {
    window.clearTimeout(timer);
    if (!stopped) {
      timer = window.setTimeout(poll, delay);
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      schedule(500);
    }
  });

  window.addEventListener("focus", () => schedule(500));
  window.addEventListener("beforeunload", () => {
    stopped = true;
    window.clearTimeout(timer);
    window.clearTimeout(eventTimer);
  });

  watchEditorChanges();
  schedule(3000);
})();
