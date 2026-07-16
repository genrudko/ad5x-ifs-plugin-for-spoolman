# AD5X IFS Plugin for Spoolman

Русская документация | [English](README.md)

Независимый плагин сообщества для **Flashforge Adventurer 5X / AD5X с Z-Mod**, который синхронизирует активный канал IFS с активной катушкой в **Moonraker/Spoolman**.

> **Бета-версия.** Проект не связан с Flashforge, Spoolman, Moonraker, Fluidd или Z-Mod и не является официально поддерживаемым ими продуктом.

## Перед установкой обязательно нужен Spoolman

Плагин **не устанавливает Spoolman** и не может работать без него.

До установки плагина необходимо:

1. установить и запустить Spoolman на ПК, NAS, Raspberry Pi, домашнем сервере или VPS;
2. добавить URL сервера Spoolman в `moonraker.conf`;
3. перезапустить Moonraker;
4. убедиться, что Moonraker возвращает `"spoolman_connected": true`.

Подробная пошаговая инструкция: [обязательная настройка Spoolman](docs/spoolman_RU.md).

## Возможности

- Определение активного канала IFS на AD5X.
- Назначение катушки Spoolman каждому из четырёх каналов.
- Автоматическое переключение активной катушки Moonraker после подтверждённой смены канала.
- Защита от дребезга и ложных переключений несколькими контрольными чтениями.
- Пропуск лишнего запроса, когда нужная катушка уже активна.
- Повторные попытки синхронизации и пауза между реальными переключениями.
- Отдельный веб-интерфейс на порту `7913`.
- Карточка **AD5X IFS** и управление её размещением во Fluidd.
- API состояния, конфигурации и диагностики.
- Структурированный журнал событий с ротацией.
- Скрипты установки, обновления, проверки состояния и удаления.

## Требования

- Flashforge AD5X / Adventurer 5X.
- Установленный чистый Z-Mod с рабочими Moonraker и Fluidd.
- Предварительно установленный и настроенный Spoolman.
- Активное соединение Moonraker со Spoolman.
- Root-доступ к принтеру по SSH.
- Доступ принтера к `raw.githubusercontent.com`.

## Одна команда для установки и обновления

Подключитесь к принтеру по SSH как `root` и вставьте:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

Параметр `?cb=$(date +%s)` предотвращает получение старой закэшированной версии установщика.

Скрипт самостоятельно:

- проверит, что запущен Moonraker;
- проверит реальное подключение Moonraker к Spoolman;
- загрузит все необходимые файлы напрямую с `raw.githubusercontent.com` без `git` и `codeload.github.com`;
- добавит cache-busting к каждому загружаемому файлу;
- определит, установлен ли плагин ранее;
- при новой установке запустит `install.sh`;
- при существующей установке запустит безопасный `update.sh` с резервной копией, health-check и автоматическим откатом.

`config.json` и `assignments.json` при обновлении сохраняются. Klipper, MCU, Moonraker и сам Z-Mod не удаляются и не переустанавливаются.

После установки или обновления откройте:

```text
http://IP_ПРИНТЕРА:7913/
```

Подробная инструкция: [docs/installation_RU.md](docs/installation_RU.md).

## Проверка состояния

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## Ручное обновление

При необходимости можно загрузить свежую копию репозитория, перейти в её каталог и выполнить:

```sh
./update.sh --dry-run
./update.sh
```

Перед обновлением создаётся резервная копия. При неудачном запуске или провале health-check выполняется автоматический откат.

## Удаление

С сохранением пользовательских данных в отдельной резервной папке:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление вместе с данными:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```

## Версии

- Пакет и служебные скрипты: `0.6.0-beta`
- Backend: `0.5.0-beta`

## Документация

- [Обязательная настройка Spoolman](docs/spoolman_RU.md)
- [Установка и обновление](docs/installation_RU.md)
- [Настройка плагина](docs/configuration_RU.md)
- [Интеграция с Fluidd](docs/fluidd-integration_RU.md)
- [HTTP API](docs/api_RU.md)
- [Архитектура](docs/architecture_RU.md)
- [Диагностика неисправностей](docs/troubleshooting_RU.md)
- [Безопасность](SECURITY_RU.md)

## Лицензия

MIT. Юридически значимый текст лицензии находится в [LICENSE](LICENSE).
