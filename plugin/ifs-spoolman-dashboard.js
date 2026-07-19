(() => {
  "use strict";

  const CARD_ID = "ifs-spoolman-fluidd-card";
  const BUTTON_ID = "ifs-spoolman-collapse-button";
  const ACTIONS_CLASS = "ifs-spoolman-head-actions";
  const STYLE_ID = "ifs-spoolman-dashboard-style";
  const COLLAPSED_CLASS = "ifs-spoolman-is-collapsed";
  const STORAGE_KEY = "ifsSpoolmanCollapsedV1";

  let observer = null;
  let timer = null;
  let scheduled = false;

  function isCollapsed() {
    return localStorage.getItem(STORAGE_KEY) === "true";
  }

  function setCollapsed(value) {
    localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
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

  function dashboardIsVisible() {
    return visibleDashboardColumns().length > 0;
  }

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${CARD_ID}[hidden] {
        display: none !important;
      }

      #${CARD_ID}.${COLLAPSED_CLASS} .ifssm-slots,
      #${CARD_ID}.${COLLAPSED_CLASS} .ifssm-detail {
        display: none !important;
      }

      #${CARD_ID}.${COLLAPSED_CLASS} .ifssm-head {
        margin-bottom: -12px !important;
        border-bottom-color: transparent !important;
      }

      #${CARD_ID} .${ACTIONS_CLASS} {
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        gap: 8px;
        flex: 0 0 auto;
        margin-left: auto;
      }

      #${BUTTON_ID} {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        width: 32px;
        height: 32px;
        margin: 0;
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: inherit;
        cursor: pointer;
        opacity: .72;
      }

      #${BUTTON_ID}:hover {
        background: rgba(255,255,255,.08);
        opacity: 1;
      }

      #${BUTTON_ID} svg {
        display: block;
        width: 18px;
        height: 18px;
        fill: currentColor;
        pointer-events: none;
        transition: transform .16s ease;
      }

      #${CARD_ID}.${COLLAPSED_CLASS} #${BUTTON_ID} svg {
        transform: rotate(180deg);
      }
    `;

    document.head.appendChild(style);
  }

  function updateButton(button, collapsed) {
    const title = collapsed ? "Развернуть" : "Свернуть";
    button.title = title;
    button.setAttribute("aria-label", title);
    button.setAttribute("aria-expanded", collapsed ? "false" : "true");
  }

  function createCollapseButton(card) {
    const header = card.querySelector(".ifssm-head");
    if (!header) return null;

    const manageButton = header.querySelector(".ifssm-manage");
    if (!manageButton) return null;

    let actions = header.querySelector(`.${ACTIONS_CLASS}`);
    if (!actions) {
      actions = document.createElement("div");
      actions.className = ACTIONS_CLASS;
      header.insertBefore(actions, manageButton);
      actions.appendChild(manageButton);
    }

    let button = actions.querySelector(`#${BUTTON_ID}`);
    if (button) return button;

    button = document.createElement("button");
    button.id = BUTTON_ID;
    button.type = "button";
    button.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.41 14.59 12 10l4.59 4.59L18 13.17l-6-6-6 6z"/>
      </svg>
    `;

    button.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();

      const next = !card.classList.contains(COLLAPSED_CLASS);
      card.classList.toggle(COLLAPSED_CLASS, next);
      setCollapsed(next);
      updateButton(button, next);
    });

    actions.appendChild(button);
    return button;
  }

  function syncCard() {
    scheduled = false;
    installStyles();

    const cards = document.querySelectorAll(`#${CARD_ID}`);
    const dashboardVisible = dashboardIsVisible();

    cards.forEach((card, index) => {
      if (index > 0) {
        card.remove();
        return;
      }

      card.hidden = !dashboardVisible;

      const collapsed = isCollapsed();
      card.classList.toggle(COLLAPSED_CLASS, collapsed);

      const button = createCollapseButton(card);
      if (button) updateButton(button, collapsed);
    });
  }

  function scheduleSync() {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(syncCard, 80);
  }

  function start() {
    installStyles();
    syncCard();

    observer = new MutationObserver(scheduleSync);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style", "hidden"]
    });

    window.addEventListener("hashchange", scheduleSync);
    window.addEventListener("popstate", scheduleSync);
    window.addEventListener("resize", scheduleSync);

    timer = window.setInterval(syncCard, 1500);

    window.addEventListener("beforeunload", () => {
      if (observer) observer.disconnect();
      if (timer !== null) window.clearInterval(timer);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
