(() => {
  "use strict";

  const POLL_INTERVAL_MS = 15000;
  const ACTIVE_CLASS = "active";
  const EMPTY_CLASS = "empty";
  const DIRTY_CLASS = "ifs-editor-dirty";

  let stopped = false;
  let requestRunning = false;
  let dirty = false;
  let lastSignature = null;
  let timer = null;

  function api(path) {
    return fetch(path, { cache: "no-store" }).then(async response => {
      let payload = {};
      try {
        payload = await response.json();
      } catch (_) {
        // The caller handles an empty payload as an unavailable state.
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

  async function poll() {
    if (stopped || requestRunning || document.hidden) {
      schedule();
      return;
    }

    requestRunning = true;
    try {
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
          return;
        }
      }
    } catch (_) {
      // Existing page status remains visible. The next cycle retries.
    } finally {
      requestRunning = false;
      schedule();
    }
  }

  function schedule(delay = POLL_INTERVAL_MS) {
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
  });

  watchEditorChanges();
  schedule(5000);
})();
