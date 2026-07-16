# Диагностика неисправностей

[English](troubleshooting.md)

## Полная проверка состояния

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## Веб-интерфейс не открывается

Проверьте, что процесс запущен и порт `7913` доступен. Затем просмотрите:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/ifs_spoolman.log
```

## Health имеет статус `degraded` или `error`

Откройте:

```text
http://IP_ПРИНТЕРА:7913/api/health
```

Проверьте отдельные компоненты `ifs_sensor`, `moonraker` и `spoolman`, затем журнал событий:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/events.log
```

## Карточка Fluidd отсутствует

Повторно примените интеграцию запуском плагина:

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

После этого обновите Fluidd без использования кэша браузера.

## Активируется неверная катушка

Проверьте назначения в веб-интерфейсе или `assignments.json`. Сравните физически активный канал с полями `raw_active_slot` и `confirmed_active_slot` в `/api/status`.

## Обновление завершилось ошибкой

Резервные копии находятся в:

```text
/usr/data/config/mod_data/ifs_spoolman/backups/
```

Updater пытается выполнить откат автоматически. После него проверьте `status.sh` и оба журнала.
