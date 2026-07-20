(() => {
  "use strict";

  const CARD_ID = "ifs-spoolman-fluidd-card";
  const MANAGER_URL = `${location.protocol}//${location.hostname}:7913/manager`;

  document.addEventListener("click", event => {
    const button = event.target && event.target.closest
      ? event.target.closest(`#${CARD_ID} .ifssm-manage`)
      : null;

    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    window.open(MANAGER_URL, "_blank", "noopener");
  }, true);
})();
