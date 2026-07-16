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

Пока возвращается `false`, ошибка или пустой ответ, устанавливать плагин рано.

## 2. Рекомендуемая установка одной командой

Подключитесь к принтеру по SSH как `root` и вставьте:

```sh
wget -qO /tmp/ad5x-ifs-install.sh https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/main/zmod-install.sh && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

Этот способ рассчитан именно на **чистый Z-Mod**:

- не требует установленного `git`;
- использует штатный `wget`;
- не использует неподдерживаемый BusyBox `tar -z`;
- отдельно распаковывает gzip-поток командой `gzip -dc`;
- проверяет Moonraker и подключение Spoolman до копирования файлов;
- устанавливает плагин в `/usr/data/config/mod_data/ifs_spoolman`.

После успешной установки откройте:

```text
http://IP_ПРИНТЕРА:7913/
```

Проверьте состояние:

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 3. Ручная загрузка без git

Этот вариант полезен для диагностики или ручного обновления.

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman-main ad5x-ifs-plugin-main.tar.gz
wget -O ad5x-ifs-plugin-main.tar.gz https://codeload.github.com/genrudko/ad5x-ifs-plugin-for-spoolman/tar.gz/refs/heads/main
mkdir -p ad5x-ifs-download
gzip -dc ad5x-ifs-plugin-main.tar.gz | tar -C ad5x-ifs-download -xf -
cd ad5x-ifs-download/ad5x-ifs-plugin-for-spoolman-main
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

Почему не используется `tar -xzf`: встроенный BusyBox `tar` на некоторых сборках Z-Mod не поддерживает ключ `-z`.

## 4. Установка через git clone

Используйте этот вариант только когда команда `git --version` действительно работает на принтере.

Проверка:

```sh
git --version
```

Клонирование и установка:

```sh
cd /usr/data
rm -rf ad5x-ifs-plugin-for-spoolman
git clone https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
cd ad5x-ifs-plugin-for-spoolman
chmod +x install.sh update.sh scripts/*.sh
./install.sh
```

На чистом Z-Mod `git` может отсутствовать. В этом случае ничего дополнительно устанавливать не требуется — используйте рекомендуемую установку через `wget`.

## 5. Что делает install.sh

Установщик:

1. проверяет структуру загруженного репозитория;
2. создаёт рабочий каталог;
3. копирует backend, веб-интерфейс, Fluidd-card и служебные скрипты;
4. создаёт отсутствующие `config.json` и `assignments.json` из примеров;
5. не перезаписывает существующие назначения и настройки;
6. устанавливает интеграцию Fluidd;
7. запускает только процесс AD5X IFS Plugin.

Klipper, MCU и сам принтер не перезапускаются.

Для копирования без запуска сервиса:

```sh
./install.sh --no-start
```

## 6. Обновление

Сначала загрузите свежую копию репозитория — через `git pull`, новую ручную загрузку или повторную загрузку архива.

При использовании git:

```sh
cd /usr/data/ad5x-ifs-plugin-for-spoolman
git pull
./update.sh --dry-run
./update.sh
```

При использовании архива перейдите в каталог новой распакованной версии и выполните:

```sh
./update.sh --dry-run
./update.sh
```

Процесс обновления:

1. проверяет структуру исходного пакета;
2. создаёт резервную копию рабочих файлов и пользовательских настроек;
3. останавливает только процесс плагина;
4. копирует новую версию;
5. запускает плагин;
6. проверяет `/api/health`;
7. автоматически откатывается при ошибке.

## 7. Управление сервисом

```sh
/usr/data/config/mod_data/ifs_spoolman/start.sh
/usr/data/config/mod_data/ifs_spoolman/stop.sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

## 8. Удаление

С резервной копией настроек и журналов:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление без сохранения пользовательских данных:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
