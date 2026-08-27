# Диагностика неисправностей

[English](troubleshooting.md)

## Плагин не работает после перезагрузки или выключения

Сначала выполните:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Проверьте разделы `Z-Mod power-on hook`, `Process`, `API health` и последние строки `boot.log`.

Автозапуск должен быть зарегистрирован в штатном пользовательском файле Z-Mod:

```text
/usr/data/config/mod_data/power_on.sh
```

В нём должен быть ровно один блок между маркерами:

```text
# >>> AD5X IFS Plugin for Spoolman >>>
# <<< AD5X IFS Plugin for Spoolman <<<
```

Если блок отсутствует, повторно запустите установщик/обновление release-линии. Не нужно вручную перезаписывать `power_on.sh`.

Для диагностики старта:

```sh
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/boot.log
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/ifs_spoolman.log
tail -n 100 /usr/data/config/mod_data/ifs_spoolman/events.log
```

Нормальная загрузка Z-Mod может включать переход от родного экрана к альтернативному экрану. Ошибки serial в момент такого переключения сами по себе не являются доказательством сбоя этого плагина.

## Web UI на порту 7913 не открывается

Проверьте backend:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
wget -qO- http://127.0.0.1:7913/api/health
```

Если процесс отсутствует, запустите:

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

`start.sh` ждёт появления процесса Moonraker при обычной загрузке. Если Moonraker вообще не запускается, сначала исправьте сам Z-Mod/Moonraker.

## Fluidd-карточка отсутствует или выглядит повреждённой

`status.sh` проверяет четыре части интеграции: `card`, `layout`, `dashboard`, `selection`.

Повторный запуск backend идемпотентно переустанавливает актуальные JS-файлы и очищает старые варианты имён. При удалении плагина удаляются также legacy `visibility`/`controls` файлы и теги.

После обновления Fluidd выполните жёсткое обновление страницы браузера (`Ctrl+F5`).

## Spoolman не подключён

Проверьте:

```sh
wget -qO- http://127.0.0.1:7125/server/spoolman/status
```

Ожидается `"spoolman_connected": true`.

Плагин не устанавливает и не заменяет Spoolman. Если Moonraker не подключён к нему, исправьте URL/доступность Spoolman до переустановки плагина.

## Активная катушка не переключается

Откройте:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Проверьте `active_slot`, `moonraker_spool_id`, назначения слотов, `last_error` и `events.log`.

Backend подтверждает физическую смену канала несколькими чтениями и выполняет повторные попытки синхронизации. Если активному IFS-слоту катушка не назначена, переключение намеренно пропускается.

## Несколько процессов backend

`status.sh` явно сообщает `multiple backend processes detected`. Безопасно выполните:

```sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
```

`stop.sh` сверяет `/proc/PID/cmdline` и не завершает посторонний процесс только из-за совпадения старого PID.
