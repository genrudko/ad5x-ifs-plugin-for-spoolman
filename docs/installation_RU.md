# Установка и обновление на Z-Mod

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

## 2. Первичная установка: одна команда по SSH

Подключитесь к принтеру как `root` и выполните:

```sh
rm -f /tmp/ad5x-ifs-install.sh && wget -qO /tmp/ad5x-ifs-install.sh "https://raw.githubusercontent.com/genrudko/ad5x-ifs-plugin-for-spoolman/release/standalone-0.6.x/zmod-install.sh?cb=$(date +%s)" && chmod +x /tmp/ad5x-ifs-install.sh && /tmp/ad5x-ifs-install.sh
```

`release/standalone-0.6.x` — поддерживаемая линия standalone-плагина. Параметр `?cb=$(date +%s)` защищает от старой закэшированной копии bootstrap-скрипта.

Bootstrap делает только первичную привязку к Z-Mod:

1. проверяет Moonraker и Spoolman;
2. регистрирует управляемый блок `[update_manager ad5x_ifs_spoolman]` в `/usr/data/config/mod_data/user.moonraker.conf`;
3. создаёт Git checkout в `/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman` через Git внутри окружения Z-Mod;
4. включает плагин через штатный `plugins.sh` Z-Mod;
5. если обнаружен старый raw-file runtime, переводит его на новую схему через транзакционный `update.sh`;
6. сохраняет пользовательские `config.json`, `assignments.json`, `power_on.sh` и Moonraker-конфиг;
7. устанавливает/восстанавливает нативную интеграцию Fluidd.

Runtime остаётся отдельно:

```text
/usr/data/config/mod_data/ifs_spoolman
```

Git source:

```text
/usr/data/config/mod_data/plugins/ad5x_ifs_spoolman
```

## 3. Все следующие обновления — через Fluidd

После регистрации updater повторно запускать SSH-команду не требуется.

Откройте:

**Fluidd → Обновления ПО → ad5x_ifs_spoolman**

и нажмите **Обновление**.

Moonraker выполняет Git update source checkout, после чего Z-Mod вызывает корневой `update.sh` из репозитория. `update.sh`:

1. создаёт резервную копию управляемого runtime и внешних файлов, которые меняет плагин;
2. останавливает только backend плагина;
3. применяет новую версию runtime;
4. восстанавливает/обновляет boot-hook;
5. запускает backend;
6. проверяет `/api/health` через Python Moonraker и валидирует поле `application`;
7. при ошибке автоматически возвращает предыдущий рабочий runtime.

Существующие настройки и назначения катушек сохраняются.

## 4. Почему update_manager использует `channel: dev`

Это **не означает экспериментальную пользовательскую ветку**. Пользовательская линия жёстко закреплена за `release/standalone-0.6.x`.

Причина техническая: Z-Mod для plugin updater с `channel: stable` выполняет generic `reset_git.sh`, который сбрасывает checkout к глобально последнему Git-тегу. В репозитории есть отдельный non-version тег `fluidd-compatibility`, поэтому такой reset может выбрать не релиз standalone-плагина.

Поэтому production bootstrap регистрирует:

```ini
[update_manager ad5x_ifs_spoolman]
type: git_repo
channel: dev
path: /root/printer_data/config/mod_data/plugins/ad5x_ifs_spoolman
origin: https://github.com/genrudko/ad5x-ifs-plugin-for-spoolman.git
is_system_service: False
primary_branch: release/standalone-0.6.x
```

Стабильность контролируется release-веткой, а `channel: dev` используется только как branch-tracking режим Moonraker.

## 5. Автозапуск

Плагин добавляет только собственный отмеченный блок в:

```text
/usr/data/config/mod_data/power_on.sh
```

Чужой пользовательский код не заменяется. После холодного старта backend автоматически поднимается и сам восстанавливает связь с Moonraker/Spoolman, если они стали доступны чуть позже.

## 6. Проверка состояния

```sh
/usr/data/config/mod_data/ifs_spoolman/status.sh
```

Ожидается:

- `Package version: 0.6.6-beta`;
- `Status: RUNNING`;
- API `status: ok`;
- Spoolman connected;
- `Native Fluidd: installed` при доступной совместимой сборке;
- `Legacy Fluidd injection: clean` при нативной интеграции.

## 7. Проверенная совместимость

Релиз `0.6.6-beta` аппаратно проверен на AD5X с Z-Mod `1.7.3-1`:

- миграция Z-Mod пережита без потери runtime/config/assignments;
- Git update через Moonraker успешно вызвал `update.sh`;
- health gate прошёл;
- после реального cold boot updater снова появился во Fluidd;
- следующее обновление было обнаружено и установлено из Fluidd.

## 8. Отключение и удаление

Z-Mod `DISABLE_PLUGIN` удаляет include и вызывает корневой `uninstall.sh`. Git checkout не удаляется самим `plugins.sh`, поэтому source/update-manager сохраняются для последующего включения.

Ручное удаление runtime с сохранением пользовательских данных:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes
```

Полное удаление runtime вместе с данными:

```sh
/usr/data/config/mod_data/ifs_spoolman/uninstall.sh --yes --purge
```
