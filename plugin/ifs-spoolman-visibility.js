(() => {
  "use strict";

  const ROOT_CLASS = "ifs-spoolman-dashboard-active";
  const STYLE_ID = "ifs-spoolman-visibility-style";
  const CARD_ID = "ifs-spoolman-fluidd-card";
  const DIALOG_ID = "ifs-spoolman-layout-dialog";

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      html:not(.${ROOT_CLASS}) #${CARD_ID},
      html:not(.${ROOT_CLASS}) #${DIALOG_ID} {
        display: none !important;
      }
    `;
    document.head.appendChild(style);
  }

  function isDashboardVisible() {
    return Array.from(
      document.querySelectorAll(".app-draggable.list-group")
    ).some(column => {
      const rect = column.getBoundingClientRect();
      return column.isConnected && rect.width > 0 && rect.height > 0;
    });
  }

  function updateVisibility() {
    document.documentElement.classList.toggle(
      ROOT_CLASS,
      isDashboardVisible()
    );
  }

  function start() {
    installStyle();
    updateVisibility();

    const observer = new MutationObserver(updateVisibility);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "style"]
    });

    window.addEventListener("hashchange", updateVisibility);
    window.addEventListener("popstate", updateVisibility);
    window.addEventListener("resize", updateVisibility);
    window.setInterval(updateVisibility, 1500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
