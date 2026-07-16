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
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

Параметр `?cb=$(date +%s)` добавляет уникальное значение к URL и не позволяет прокси или CDN вернуть старую закэшированную версию установщика.

Этот способ рассчитан именно на **чистый Z-Mod**:

- не требует установленного `git`;
- использует штатный `wget`;
- не использует `codeload.github.com`, с которым встроенный TLS-клиент Z-Mod может разрывать соединение;
- загружает необходимые файлы напрямую с `raw.githubusercontent.com`;
- добавляет cache-busting к каждому файлу;
- проверяет Moonraker и подключение Spoolman до изменения файлов;
- автоматически определяет новую или существующую установку.

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
4. запускает плагин;
5. проверяет `/api/health`;
6. автоматически восстанавливает предыдущую версию при ошибке.

Существующие настройки и назначения катушек сохраняются. Klipper, MCU, Moonraker, Spoolman и сам Z-Mod не удаляются и не переустанавливаются.

После успешной установки или обновления откройте:

```text
http://IP_ПРИНТЕРА:7913/
```

Проверьте состояние:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 3. Почему не используется архив codeload.github.com

На некоторых сборках чистого Z-Mod встроенный `wget` успешно подключается к `raw.githubusercontent.com`, но получает TLS alert 80 или `Connection reset by peer` при скачивании архива с `codeload.github.com`.

Поэтому рекомендуемый установщик не скачивает ZIP/TAR-архив и не распаковывает его. Он получает только необходимые файлы напрямую с raw-домена.

## 4. Установка через git clone

Используйте этот вариант только когда команда `git --version` действительно работает на принтере.

Проверка:

```sh
git --version
```

Новая установка:

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman
git clone https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
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

## 5. Что делает install.sh

Установщик:

1. проверяет структуру загруженного набора файлов;
2. создаёт рабочий каталог;
3. копирует backend, веб-интерфейс, Fluidd-card и служебные скрипты;
4. создаёт отсутствующие `config.json` и `assignments.json` из примеров;
5. не перезаписывает существующие назначения и настройки;
6. устанавливает интеграцию Fluidd;
7. запускает только процесс AD5X IFS Plugin.

Для копирования без запуска сервиса:

```sh
./install.sh --no-start
```

Для обновления поверх существующей версии используйте `update.sh`, а не `install.sh`.

## 6. Управление сервисом

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 7. Удаление

С резервной копией настроек и журналов:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление без сохранения пользовательских данных:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
