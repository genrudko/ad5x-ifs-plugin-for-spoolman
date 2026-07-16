# Интеграция с Fluidd

[English](fluidd-integration.md)

Плагин добавляет в `index.html` Fluidd два локальных JavaScript-файла:

- `ifs-spoolman-card-v10.js`;
- `ifs-spoolman-layout-v2.js`.

Карточка показывает активный канал IFS, назначенную катушку и состояние синхронизации, а также открывает отдельный веб-интерфейс управления.

Модуль layout управляет расположением карточки и хранит пользовательские настройки размещения в local storage браузера.

Установщик удаляет старые файлы `ifs-spoolman-card*.js` и `ifs-spoolman-layout*.js`. Скрипт `uninstall_fluidd_card.sh` удаляет и теги подключения, и сами статические файлы.

Обновление Z-Mod или Fluidd может заменить `index.html`. Поэтому `boot_start.sh` повторно применяет интеграцию при запуске плагина.
