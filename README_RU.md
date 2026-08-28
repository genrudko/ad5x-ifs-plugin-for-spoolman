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
- Повторные попытки синхронизации и пропуск лишнего переключения уже активной катушки.
- Отдельный веб-интерфейс на порту `7913`.
- Нативная карточка **AD5X IFS Spoolman** во Fluidd с legacy fallback только при необходимости.
- Структурированный журнал событий и диагностический API.
- Штатный автозапуск через пользовательский `mod_data/power_on.sh` Z-Mod.
- Git-managed установка: после первой SSH-команды дальнейшие обновления идут через Moonraker/Fluidd Update Manager.
- Транзакционное обновление с резервной копией, health-check и автоматическим rollback runtime.

## Требования

- Flashforge AD5X / Adventurer 5X.
- Z-Mod с рабочими Moonraker и Fluidd. Проверено на Z-Mod `1.7.3-1`.
- Предварительно установленный и настроенный Spoolman.
- Активное соединение Moonraker со Spoolman.
- Root-доступ к принтеру по SSH для первой установки.
- Доступ принтера к GitHub/raw.githubusercontent.com.

## Одна SSH-команда для первичной установки

Подключитесь к принтеру по SSH как `root` и вставьте:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/release/standalone-0.6.x/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

Параметр `?cb=$(date +%s)` предотвращает получение старой закэшированной версии bootstrap-скрипта.

Установщик:

- проверяет Moonraker и реальное подключение к Spoolman;
- регистрирует `[update_manager ad5x_ifs_spoolman]` в пользовательском `mod_data/user.moonraker.conf`;
- создаёт постоянный Git checkout в `mod_data/plugins/ad5x_ifs_spoolman` через окружение Z-Mod;
- включает плагин через штатный `plugins.sh` Z-Mod;
- при переходе со старой raw-file установки использует безопасный `update.sh`, сохраняя `config.json`, `assignments.json`, `power_on.sh` и пользовательский Moonraker-конфиг;
- устанавливает/восстанавливает нативную интеграцию Fluidd.

После первичной установки Git source находится здесь:

```text
/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman
```

Runtime находится здесь:

```text
/usr/data/config/mod_data/ifs_spoolman
```

## Дальнейшие обновления — из Fluidd

После того как Moonraker увидел updater, повторно заходить по SSH не нужно:

**Fluidd → Обновления ПО → ad5x_ifs_spoolman → Обновление**.

Moonraker делает Git update, затем Z-Mod вызывает репозиторный `update.sh`. Runtime обновляется транзакционно; `config.json` и `assignments.json` сохраняются. При провале запуска или health-gate предыдущий рабочий runtime восстанавливается автоматически.

Поддерживаемая пользовательская линия — `release/standalone-0.6.x`. Внутренний Moonraker channel намеренно зарегистрирован как `dev`, чтобы Z-Mod следовал именно этой ветке и не выполнял generic reset к постороннему non-version Git-тегу.

## Проверка состояния

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

`status.sh` проверяет package version, boot-hook, процесс backend, API, Spoolman sync, нативную интеграцию Fluidd и отсутствие legacy-дубликата.

## Веб-интерфейс

```text
http://IP_ПРИНТЕРА:7913/
```

## Отключение и удаление

Штатный Z-Mod `DISABLE_PLUGIN` вызывает корневой `uninstall.sh`: активный runtime удаляется, но Git checkout и update-manager остаются, поэтому плагин можно снова включить штатно.

Для ручного удаления runtime с сохранением пользовательских данных:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление runtime вместе с данными:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```

## Версии

- Пакет/runtime: `0.6.6-beta`
- Проверенная линия Z-Mod: `1.7.3-1`
- Проверенная нативная интеграция Fluidd: `v1.37.4`, patch revision 4

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
