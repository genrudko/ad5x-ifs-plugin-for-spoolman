# Участие в разработке

[English](CONTRIBUTING.md)

Проект находится в beta-стадии. В отчёте об ошибке укажите:

- модель принтера и версию Z-Mod;
- версии пакета и backend плагина;
- вывод `/api/health` без приватных сетевых данных;
- относящиеся к ошибке строки из `events.log` и `ifs_spoolman.log`;
- точную последовательность воспроизведения.

Перед отправкой изменений выполните:

```sh
python3 -m py_compile plugin/ifs_spoolman.py
for file in install.sh update.sh scripts/*.sh; do sh -n "$file"; done
```

Не добавляйте в репозиторий `config.json`, `assignments.json`, журналы, PID-файлы, резервные копии, реальные адреса Spoolman, пароли, токены и приватные IP-адреса.
