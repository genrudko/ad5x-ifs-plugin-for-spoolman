# Установка и обновление на чистом Z-Mod

[English](installation.md)

## 1. Сначала установите и настройте Spoolman

**Это обязательное условие.** Плагин не устанавливает Spoolman и не может работать без активного соединения Moonraker со Spoolman.

Перед продолжением выполните [инструкцию по настройке Spoolman](spoolman_RU.md).

Быстрая проверка на принтере:

```sh
wget -qO- http://127.0.0.1:7125/server/spoolman/status
```

В ответе должно быть:

```json
"spoolman_connected": true
```

Пока возвращается `false`, ошибка или пустой ответ, устанавливать или обновлять плагин рано.

## 2. Рекомендуемая команда для установки и обновления

Подключитесь к принтеру по SSH как `root` и вставьте:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/release/standalone-0.6.x/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

`release/standalone-0.6.x` — отдельная поддерживаемая линия исходного standalone-плагина. Экспериментальные Filament Manager ветки в неё не входят.

Параметр `?cb=$(date +%s)` добавляет уникальное значение к URL и не позволяет прокси или CDN вернуть старую закэшированную версию установщика.

Этот способ рассчитан именно на **чистый Z-Mod**:

- не требует установленного `git`;
- использует штатный `wget`;
- не использует `codeload.github.com`, с которым встроенный TLS-клиент Z-Mod может разрывать соединение;
- загружает необходимые файлы напрямую с `raw.githubusercontent.com`;
- добавляет cache-busting к каждому файлу;
- проверяет Moonraker и подключение Spoolman до изменения файлов;
- автоматически определяет новую или существующую установку;
- регистрирует автозапуск через штатный пользовательский `mod_data/power_on.sh` Z-Mod.

Автозапуск добавляется в отдельном отмеченном блоке. Существующее пользовательское содержимое `power_on.sh` не заменяется. Повторная установка обновляет тот же блок и не создаёт дубликаты.

### Когда плагин ещё не установлен

Скрипт запускает `install.sh` и устанавливает плагин в:

```text
/usr/data/config/mod_data/ifs_spoolman
```

### Когда плагин уже установлен

Скрипт запускает `update.sh`, который:

1. создаёт резервную копию рабочих файлов, `config.json` и `assignments.json`;
2. останавливает только процесс плагина;
3. копирует новую версию;
4. восстанавливает/обновляет штатный boot-hook;
5. запускает плагин;
6. проверяет `/api/health`;
7. автоматически восстанавливает предыдущую версию при ошибке.

Существующие настройки и назначения катушек сохраняются. Klipper, MCU, Moonraker, Spoolman и сам Z-Mod не удаляются и не переустанавливаются.

После успешной установки или обновления откройте:

```text
http://IP_ПРИНТЕРА:7913/
```

Проверьте состояние:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

`status.sh` проверяет процесс, принадлежность PID, отсутствие дубликатов backend, boot-hook, API и компоненты Fluidd-интеграции. Также показывает последние записи `boot.log` и `events.log`.

## 3. Автозапуск и порядок старта Z-Mod

Z-Mod выполняет пользовательский код включения из:

```text
/usr/data/config/mod_data/power_on.sh
```

Плагин добавляет туда только собственный блок между маркерами `AD5X IFS Plugin for Spoolman`. Блок запускает `ifs_spoolman/start.sh` в фоне, поэтому не блокирует остальные пользовательские действия при старте.

`start.sh` допускает обычную гонку загрузки и ждёт появления процесса Moonraker до 120 секунд. Внутри Z-Mod backend дополнительно ждёт готовности HTTP API Moonraker, но после таймаута всё равно запускается: цикл мониторинга сам восстановит связь, когда Moonraker/Spoolman станет доступен.

## 4. Почему не используется архив codeload.github.com

На некоторых сборках чистого Z-Mod встроенный `wget` успешно подключается к `raw.githubusercontent.com`, но получает TLS alert 80 или `Connection reset by peer` при скачивании архива с `codeload.github.com`.

Поэтому рекомендуемый установщик не скачивает ZIP/TAR-архив и не распаковывает его. Он получает только необходимые файлы напрямую с raw-домена.

## 5. Установка через git clone

Используйте этот вариант только когда команда `git --version` действительно работает на принтере.

Новая установка:

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman
git clone --branch release/standalone-0.6.x https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
cd ad5x-ifs-plugin-for-spoolman
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

Обновление существующей установки:

```sh
cd /usr/data/ad5x-ifs-plugin-for-spoolman
git pull
./update.sh --dry-run
./update.sh
```

На чистом Z-Mod `git` может отсутствовать. В этом случае ничего дополнительно устанавливать не требуется — используйте рекомендуемую команду через `wget`.

## 6. Управление сервисом

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

`start.sh` и `stop.sh` проверяют командную строку процесса, а не только существование PID. Это защищает от ложного «уже запущен» и от остановки постороннего процесса после повторного использования PID.

## 7. Удаление

С резервной копией настроек и журналов:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление без сохранения пользовательских данных:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```

Удаление сначала убирает только управляемый блок плагина из `mod_data/power_on.sh`, затем останавливает backend и удаляет Fluidd-интеграцию. Чужой пользовательский код в `power_on.sh` не удаляется.
