# AD5X IFS Plugin for Spoolman

Русская документация | [English](README.md)

Независимый плагин сообщества для **Flashforge Adventurer 5X / AD5X с Z-Mod**, который синхронизирует активный канал IFS с активной катушкой в **Moonraker/Spoolman**.

> **Бета-версия.** Проект не связан с Flashforge, Spoolman, Moonraker, Fluidd или Z-Mod и не является официально поддерживаемым ими продуктом.

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
- Установленный Z-Mod с рабочими Moonraker и Fluidd.
- Moonraker, подключённый к серверу Spoolman.
- Root-доступ к принтеру по SSH.

## Установка

Скопируйте или клонируйте репозиторий на принтер, перейдите в его каталог и выполните:

```sh
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

Рабочие файлы устанавливаются в:

```text
/usr/data/config/mod_data/ifs_spoolman
```

Веб-интерфейс:

```text
http://IP_ПРИНТЕРА:7913/
```

Подробности: [docs/installation_RU.md](docs/installation_RU.md).

## Обновление

```sh
./update.sh --dry-run
./update.sh
```

`config.json` и `assignments.json` сохраняются. Перед обновлением создаётся резервная копия; при неудачном запуске или провале health-check выполняется автоматический откат.

## Проверка состояния

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

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

- [Установка и обновление](docs/installation_RU.md)
- [Настройка](docs/configuration_RU.md)
- [Интеграция с Fluidd](docs/fluidd-integration_RU.md)
- [HTTP API](docs/api_RU.md)
- [Архитектура](docs/architecture_RU.md)
- [Диагностика неисправностей](docs/troubleshooting_RU.md)
- [Безопасность](SECURITY_RU.md)

## Лицензия

MIT. Юридически значимый текст лицензии находится в [LICENSE](LICENSE).
