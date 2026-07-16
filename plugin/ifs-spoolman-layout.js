(() => {
  "use strict";

  const VERSION = "1.1.0";
  const CARD_ID = "ifs-spoolman-fluidd-card";
  const SETTINGS_BUTTON_ID = "ifs-spoolman-layout-button";
  const DIALOG_ID = "ifs-spoolman-layout-dialog";
  const STYLE_ID = "ifs-spoolman-layout-style";
  const STORAGE_KEY = "ifsSpoolmanFluiddLayoutV1";

  let observer = null;
  let maintenanceTimer = null;
  let scheduled = false;
  let movingCard = false;

  function getCard() {
    return document.getElementById(CARD_ID);
  }

  function getColumns() {
    return Array.from(
      document.querySelectorAll(".app-draggable.list-group")
    ).filter(column => {
      return (
        column.isConnected &&
        !column.closest(`#${CARD_ID}`) &&
        column.getBoundingClientRect().width > 0
      );
    });
  }

  function readConfig() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);

      if (!raw) {
        return null;
      }

      const parsed = JSON.parse(raw);

      if (
        !Number.isInteger(parsed.column) ||
        !Number.isInteger(parsed.position)
      ) {
        return null;
      }

      return {
        column: Math.max(0, parsed.column),
        position: Math.max(0, parsed.position)
      };
    } catch {
      return null;
    }
  }

  function writeConfig(config) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        column: config.column,
        position: config.position
      })
    );
  }

  function removeConfig() {
    localStorage.removeItem(STORAGE_KEY);
  }

  function childrenWithoutCard(column, card) {
    return Array.from(column.children).filter(child => {
      return (
        child !== card &&
        child.id !== DIALOG_ID &&
        !child.classList.contains("ifs-layout-transient")
      );
    });
  }

  function currentLocation(card) {
    const columns = getColumns();
    const columnIndex = columns.indexOf(card.parentElement);

    if (columnIndex < 0) {
      return {
        column: 0,
        position: 0
      };
    }

    const siblings = childrenWithoutCard(columns[columnIndex], card);

    let position = 0;

    for (const child of Array.from(columns[columnIndex].children)) {
      if (child === card) {
        break;
      }

      if (siblings.includes(child)) {
        position += 1;
      }
    }

    return {
      column: columnIndex,
      position
    };
  }

  function moveCard(columnIndex, positionIndex) {
    const card = getCard();
    const columns = getColumns();

    if (!card || columns.length === 0) {
      return false;
    }

    const safeColumn = Math.max(
      0,
      Math.min(columnIndex, columns.length - 1)
    );

    const targetColumn = columns[safeColumn];
    const items = childrenWithoutCard(targetColumn, card);

    const safePosition = Math.max(
      0,
      Math.min(positionIndex, items.length)
    );

    const current = currentLocation(card);

    if (
      current.column === safeColumn &&
      current.position === safePosition
    ) {
      return true;
    }

    movingCard = true;

    try {
      const referenceNode = items[safePosition] || null;
      targetColumn.insertBefore(card, referenceNode);
    } finally {
      window.setTimeout(() => {
        movingCard = false;
      }, 100);
    }

    return true;
  }

  function findNativeSpoolmanCard() {
    const cards = Array.from(
      document.querySelectorAll(".v-card, .collapsable-card")
    );

    return cards.find(card => {
      if (card.id === CARD_ID) {
        return false;
      }

      const text = String(card.textContent || "")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();

      return (
        text.includes("spoolman") &&
        (
          text.includes("сменить катушку") ||
          text.includes("remaining") ||
          text.includes("пруток")
        )
      );
    }) || null;
  }

  function restoreAutomaticLocation() {
    const card = getCard();

    if (!card) {
      return;
    }

    const nativeSpoolman = findNativeSpoolmanCard();

    if (
      nativeSpoolman &&
      nativeSpoolman.parentElement &&
      nativeSpoolman.parentElement.matches(
        ".app-draggable.list-group"
      )
    ) {
      movingCard = true;

      try {
        nativeSpoolman.insertAdjacentElement("afterend", card);
      } finally {
        window.setTimeout(() => {
          movingCard = false;
        }, 100);
      }

      return;
    }

    const columns = getColumns();

    if (columns.length > 0) {
      columns[0].appendChild(card);
    }
  }

  function applySavedLayout() {
    if (movingCard) {
      return;
    }

    const config = readConfig();

    if (!config) {
      return;
    }

    moveCard(config.column, config.position);
  }

  function installStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement("style");
    style.id = STYLE_ID;

    style.textContent = `
      #${SETTINGS_BUTTON_ID} {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        width: 32px;
        height: 32px;
        margin-left: 4px;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 7px;
        background: rgba(255,255,255,.04);
        color: inherit;
        cursor: pointer;
        opacity: .82;
        transition:
          background-color .15s ease,
          opacity .15s ease;
      }

      #${SETTINGS_BUTTON_ID}:hover {
        background: rgba(255,255,255,.09);
        opacity: 1;
      }

      #${SETTINGS_BUTTON_ID} svg {
        width: 17px;
        height: 17px;
        fill: currentColor;
      }

      #${DIALOG_ID} {
        position: fixed;
        inset: 0;
        z-index: 100000;
        display: grid;
        place-items: center;
        padding: 18px;
        background: rgba(0,0,0,.42);
        backdrop-filter: blur(1.5px);
        font-family:
          Roboto,
          "Noto Sans",
          system-ui,
          -apple-system,
          BlinkMacSystemFont,
          "Segoe UI",
          Arial,
          sans-serif;
        font-size: 14px;
        font-weight: 400;
        line-height: 1.4;
      }

      #${DIALOG_ID}[hidden] {
        display: none;
      }

      #${DIALOG_ID} .ifs-layout-panel {
        width: min(430px, 100%);
        overflow: hidden;
        border:
          1px solid
          var(--ifs-layout-border, rgba(255,255,255,.14));
        border-radius:
          var(--ifs-layout-radius, 8px);
        background:
          var(--ifs-layout-background, #303030);
        color:
          var(--ifs-layout-color, rgba(255,255,255,.88));
        box-shadow:
          var(
            --ifs-layout-shadow,
            0 16px 48px rgba(0,0,0,.38)
          );
      }

      #${DIALOG_ID} .ifs-layout-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 48px;
        padding: 0 14px;
        border-bottom:
          1px solid
          var(--ifs-layout-header-border, rgba(255,255,255,.10));
        background:
          var(
            --ifs-layout-header-background,
            rgba(255,255,255,.045)
          );
        color:
          var(--ifs-layout-header-color, inherit);
      }

      #${DIALOG_ID} .ifs-layout-title {
        font-family: inherit;
        font-size: 15px;
        font-weight: 500;
        letter-spacing: 0;
      }

      #${DIALOG_ID} .ifs-layout-close {
        width: 32px;
        height: 32px;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: inherit;
        cursor: pointer;
        font-size: 22px;
        line-height: 1;
        opacity: .72;
      }

      #${DIALOG_ID} .ifs-layout-close:hover {
        background: rgba(255,255,255,.08);
        opacity: 1;
      }

      #${DIALOG_ID} .ifs-layout-body {
        padding: 16px;
      }

      #${DIALOG_ID} .ifs-layout-description {
        margin-bottom: 16px;
        color:
          var(
            --ifs-layout-muted,
            rgba(255,255,255,.60)
          );
        font-size: 13px;
        font-weight: 400;
        line-height: 1.45;
      }

      #${DIALOG_ID} .ifs-layout-field {
        margin-bottom: 13px;
      }

      #${DIALOG_ID} .ifs-layout-label {
        display: block;
        margin-bottom: 6px;
        color:
          var(
            --ifs-layout-muted,
            rgba(255,255,255,.62)
          );
        font-size: 11px;
        font-weight: 600;
        letter-spacing: .035em;
        text-transform: uppercase;
      }

      #${DIALOG_ID} select {
        width: 100%;
        height: 40px;
        padding: 0 34px 0 11px;
        border:
          1px solid
          var(--ifs-layout-field-border, rgba(255,255,255,.13));
        border-radius: 5px;
        outline: none;
        background-color:
          var(--ifs-layout-field-background, #242424);
        color:
          var(--ifs-layout-field-color, rgba(255,255,255,.90));
        font-family: inherit;
        font-size: 14px;
        font-weight: 400;
        cursor: pointer;
      }

      #${DIALOG_ID} select:focus {
        border-color: #2196f3;
        box-shadow: 0 0 0 2px rgba(33,150,243,.18);
      }

      #${DIALOG_ID} .ifs-layout-preview {
        margin-top: 7px;
        color:
          var(
            --ifs-layout-muted,
            rgba(255,255,255,.52)
          );
        font-size: 11px;
        font-weight: 400;
      }

      #${DIALOG_ID} .ifs-layout-actions {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        padding: 12px 16px 15px;
        border-top: 1px solid rgba(255,255,255,.08);
      }

      #${DIALOG_ID} .ifs-layout-actions-right {
        display: flex;
        gap: 8px;
      }

      #${DIALOG_ID} button.ifs-layout-action {
        min-height: 36px;
        padding: 0 14px;
        border:
          1px solid
          var(--ifs-layout-button-border, rgba(255,255,255,.12));
        border-radius: 5px;
        background:
          var(
            --ifs-layout-button-background,
            rgba(255,255,255,.06)
          );
        color: inherit;
        cursor: pointer;
        font-family: inherit;
        font-size: 12px;
        font-weight: 500;
        letter-spacing: 0;
      }

      #${DIALOG_ID} button.ifs-layout-action:hover {
        background: rgba(255,255,255,.11);
      }

      #${DIALOG_ID} button.ifs-layout-primary {
        border-color: rgba(33,150,243,.45);
        background: #1976d2;
        color: #fff;
      }

      #${DIALOG_ID} button.ifs-layout-primary:hover {
        background: #1565c0;
      }

      #${DIALOG_ID} button.ifs-layout-reset {
        color: inherit;
        opacity: .82;
      }

      #${DIALOG_ID} button.ifs-layout-reset:hover {
        opacity: 1;
      }

      .theme--light #${DIALOG_ID} .ifs-layout-panel,
      .v-theme--light #${DIALOG_ID} .ifs-layout-panel {
        border-color: rgba(15,23,42,.15);
        background: #fff;
        color: rgba(15,23,42,.88);
      }

      .theme--light #${DIALOG_ID} .ifs-layout-header,
      .v-theme--light #${DIALOG_ID} .ifs-layout-header {
        border-bottom-color: rgba(15,23,42,.10);
        background: rgba(15,23,42,.035);
      }

      .theme--light #${DIALOG_ID} .ifs-layout-description,
      .theme--light #${DIALOG_ID} .ifs-layout-label,
      .theme--light #${DIALOG_ID} .ifs-layout-preview,
      .v-theme--light #${DIALOG_ID} .ifs-layout-description,
      .v-theme--light #${DIALOG_ID} .ifs-layout-label,
      .v-theme--light #${DIALOG_ID} .ifs-layout-preview {
        color: rgba(15,23,42,.60);
      }

      .theme--light #${DIALOG_ID} select,
      .v-theme--light #${DIALOG_ID} select {
        border-color: rgba(15,23,42,.14);
        background: #f6f7f9;
        color: rgba(15,23,42,.90);
      }

      @media (max-width: 480px) {
        #${DIALOG_ID} .ifs-layout-actions {
          flex-direction: column;
        }

        #${DIALOG_ID} .ifs-layout-actions-right {
          display: grid;
          grid-template-columns: 1fr 1fr;
        }

        #${DIALOG_ID} button.ifs-layout-action {
          width: 100%;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function positionLabel(position, total) {
    if (position === 0) {
      return "1 — вверху";
    }

    if (position === total) {
      return `${position + 1} — внизу`;
    }

    return `${position + 1}`;
  }

  function fillPositionSelect(
    select,
    columnIndex,
    preferredPosition
  ) {
    const columns = getColumns();
    const card = getCard();

    if (!select || !card || columns.length === 0) {
      return;
    }

    const safeColumn = Math.max(
      0,
      Math.min(columnIndex, columns.length - 1)
    );

    const itemCount = childrenWithoutCard(
      columns[safeColumn],
      card
    ).length;

    select.innerHTML = "";

    for (let position = 0; position <= itemCount; position += 1) {
      const option = document.createElement("option");
      option.value = String(position);
      option.textContent = positionLabel(position, itemCount);
      select.appendChild(option);
    }

    select.value = String(
      Math.max(0, Math.min(preferredPosition, itemCount))
    );
  }

  function syncDialogTheme() {
    const dialog = document.getElementById(DIALOG_ID);
    const card = getCard();

    if (!dialog || !card) {
      return;
    }

    const cardStyle = window.getComputedStyle(card);

    dialog.style.setProperty(
      "--ifs-layout-background",
      cardStyle.backgroundColor
    );

    dialog.style.setProperty(
      "--ifs-layout-color",
      cardStyle.color
    );

    dialog.style.setProperty(
      "--ifs-layout-border",
      cardStyle.borderColor
    );

    dialog.style.setProperty(
      "--ifs-layout-radius",
      cardStyle.borderRadius
    );

    dialog.style.setProperty(
      "--ifs-layout-shadow",
      cardStyle.boxShadow
    );

    const header =
      card.querySelector(".ifssm-head") ||
      card.querySelector(".ifs-card-header") ||
      card.firstElementChild;

    if (header) {
      const headerStyle = window.getComputedStyle(header);

      const headerBackground =
        headerStyle.backgroundImage !== "none"
          ? headerStyle.backgroundImage
          : headerStyle.backgroundColor;

      dialog.style.setProperty(
        "--ifs-layout-header-background",
        headerBackground
      );

      dialog.style.setProperty(
        "--ifs-layout-header-color",
        headerStyle.color
      );

      dialog.style.setProperty(
        "--ifs-layout-header-border",
        headerStyle.borderBottomColor
      );
    }

    const body =
      card.querySelector(".ifssm-detail") ||
      card.querySelector(".ifs-active-panel") ||
      card;

    const bodyStyle = window.getComputedStyle(body);

    dialog.style.setProperty(
      "--ifs-layout-field-background",
      bodyStyle.backgroundColor
    );

    dialog.style.setProperty(
      "--ifs-layout-field-color",
      cardStyle.color
    );

    dialog.style.setProperty(
      "--ifs-layout-field-border",
      bodyStyle.borderColor
    );

    dialog.style.setProperty(
      "--ifs-layout-button-background",
      bodyStyle.backgroundColor
    );

    dialog.style.setProperty(
      "--ifs-layout-button-border",
      bodyStyle.borderColor
    );

    const muted =
      window
        .getComputedStyle(
          card.querySelector(".ifssm-sub") || card
        )
        .color;

    dialog.style.setProperty(
      "--ifs-layout-muted",
      muted
    );
  }

  function closeDialog() {
    const dialog = document.getElementById(DIALOG_ID);

    if (dialog) {
      dialog.hidden = true;
    }
  }

  function openDialog() {
    const dialog = ensureDialog();
    const card = getCard();
    const columns = getColumns();

    syncDialogTheme();

    if (!dialog || !card || columns.length === 0) {
      return;
    }

    const columnSelect = dialog.querySelector(
      '[data-role="column"]'
    );

    const positionSelect = dialog.querySelector(
      '[data-role="position"]'
    );

    const preview = dialog.querySelector(
      '[data-role="preview"]'
    );

    const saved = readConfig();
    const current = currentLocation(card);
    const initial = saved || current;

    columnSelect.innerHTML = "";

    columns.forEach((column, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `Колонка ${index + 1}`;
      columnSelect.appendChild(option);
    });

    const selectedColumn = Math.max(
      0,
      Math.min(initial.column, columns.length - 1)
    );

    columnSelect.value = String(selectedColumn);

    fillPositionSelect(
      positionSelect,
      selectedColumn,
      initial.position
    );

    function updatePreview() {
      preview.textContent =
        `Карточка будет размещена: колонка ` +
        `${Number(columnSelect.value) + 1}, позиция ` +
        `${Number(positionSelect.value) + 1}.`;
    }

    columnSelect.onchange = () => {
      fillPositionSelect(
        positionSelect,
        Number(columnSelect.value),
        0
      );

      updatePreview();
    };

    positionSelect.onchange = updatePreview;
    updatePreview();

    dialog.hidden = false;
  }

  function ensureDialog() {
    let dialog = document.getElementById(DIALOG_ID);

    if (dialog) {
      return dialog;
    }

    dialog = document.createElement("div");
    dialog.id = DIALOG_ID;
    dialog.hidden = true;

    dialog.innerHTML = `
      <div
        class="ifs-layout-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ifs-layout-dialog-title"
      >
        <div class="ifs-layout-header">
          <div
            class="ifs-layout-title"
            id="ifs-layout-dialog-title"
          >
            Расположение AD5X IFS
          </div>

          <button
            class="ifs-layout-close"
            type="button"
            aria-label="Закрыть"
            title="Закрыть"
          >
            ×
          </button>
        </div>

        <div class="ifs-layout-body">
          <div class="ifs-layout-description">
            Выбери колонку Dashboard и позицию карточки.
            Настройка сохраняется только в этом браузере.
          </div>

          <div class="ifs-layout-field">
            <label class="ifs-layout-label">
              Колонка
            </label>

            <select data-role="column"></select>
          </div>

          <div class="ifs-layout-field">
            <label class="ifs-layout-label">
              Позиция в колонке
            </label>

            <select data-role="position"></select>

            <div
              class="ifs-layout-preview"
              data-role="preview"
            ></div>
          </div>
        </div>

        <div class="ifs-layout-actions">
          <button
            class="ifs-layout-action ifs-layout-reset"
            type="button"
            data-role="reset"
          >
            Автоматически
          </button>

          <div class="ifs-layout-actions-right">
            <button
              class="ifs-layout-action"
              type="button"
              data-role="cancel"
            >
              Отмена
            </button>

            <button
              class="ifs-layout-action ifs-layout-primary"
              type="button"
              data-role="save"
            >
              Сохранить
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    dialog
      .querySelector(".ifs-layout-close")
      .addEventListener("click", closeDialog);

    dialog
      .querySelector('[data-role="cancel"]')
      .addEventListener("click", closeDialog);

    dialog
      .querySelector('[data-role="save"]')
      .addEventListener("click", () => {
        const column = Number(
          dialog.querySelector('[data-role="column"]').value
        );

        const position = Number(
          dialog.querySelector('[data-role="position"]').value
        );

        writeConfig({
          column,
          position
        });

        moveCard(column, position);
        closeDialog();
      });

    dialog
      .querySelector('[data-role="reset"]')
      .addEventListener("click", () => {
        removeConfig();
        restoreAutomaticLocation();
        closeDialog();
      });

    dialog.addEventListener("click", event => {
      if (event.target === dialog) {
        closeDialog();
      }
    });

    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !dialog.hidden) {
        closeDialog();
      }
    });

    return dialog;
  }

  function installSettingsButton() {
    const card = getCard();

    if (!card) {
      return;
    }

    if (document.getElementById(SETTINGS_BUTTON_ID)) {
      return;
    }

    const header =
      card.querySelector(".ifssm-head") ||
      card.querySelector(".ifs-card-header");

    if (!header) {
      return;
    }

    const button = document.createElement("button");
    button.id = SETTINGS_BUTTON_ID;
    button.type = "button";
    button.title = "Настроить расположение карточки";
    button.setAttribute(
      "aria-label",
      "Настроить расположение карточки"
    );

    button.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M19.14 12.94a7.43 7.43 0 0 0 .05-.94 7.43 7.43 0 0 0-.05-.94l2.03-1.58a.49.49 0 0 0 .12-.62l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96a7.3 7.3 0 0 0-1.62-.94L14.4 2.8a.48.48 0 0 0-.48-.4h-3.84a.48.48 0 0 0-.48.4l-.37 2.54c-.58.24-1.12.55-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.71 8.86a.49.49 0 0 0 .12.62l2.03 1.58a7.43 7.43 0 0 0-.05.94c0 .32.02.63.05.94l-2.03 1.58a.49.49 0 0 0-.12.62l1.92 3.32c.12.22.38.31.59.22l2.39-.96c.5.39 1.04.7 1.62.94l.37 2.54c.04.23.24.4.48.4h3.84c.24 0 .44-.17.48-.4l.37-2.54c.58-.24 1.12-.55 1.62-.94l2.39.96c.21.09.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.62l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z"/>
      </svg>
    `;

    button.addEventListener("click", event => {
      event.stopPropagation();
      openDialog();
    });

    const manageButton =
      header.querySelector(".ifssm-manage") ||
      header.querySelector(".ifs-manage-button");

    if (manageButton) {
      header.insertBefore(button, manageButton);
    } else {
      header.appendChild(button);
    }
  }

  function removeDuplicateCards() {
    const cards = document.querySelectorAll(`#${CARD_ID}`);

    if (cards.length <= 1) {
      return;
    }

    Array.from(cards)
      .slice(1)
      .forEach(card => card.remove());
  }

  function maintain() {
    scheduled = false;

    installStyles();
    removeDuplicateCards();
    installSettingsButton();
    applySavedLayout();
    syncDialogTheme();
  }

  function scheduleMaintain() {
    if (scheduled || movingCard) {
      return;
    }

    scheduled = true;
    window.setTimeout(maintain, 120);
  }

  function start() {
    installStyles();
    ensureDialog();
    maintain();

    observer = new MutationObserver(scheduleMaintain);

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    maintenanceTimer = window.setInterval(
      maintain,
      2000
    );

    window.addEventListener("storage", event => {
      if (event.key === STORAGE_KEY) {
        applySavedLayout();
      }
    });

    window.addEventListener("beforeunload", () => {
      if (observer) {
        observer.disconnect();
      }

      if (maintenanceTimer !== null) {
        clearInterval(maintenanceTimer);
      }
    });

    console.info(
      `IFS Spoolman Fluidd layout v${VERSION} loaded`
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      start,
      { once: true }
    );
  } else {
    start();
  }
})();
