# Contributing

This project is in beta. Bug reports should include:

- printer and Z-Mod version;
- plugin package/backend version;
- `/api/health` output with private network details removed;
- relevant lines from `events.log` and `ifs_spoolman.log`;
- exact steps to reproduce.

Before submitting code changes:

```sh
python3 -m py_compile plugin/ifs_spoolman.py
for file in install.sh update.sh scripts/*.sh; do sh -n "$file"; done
```

Do not commit `config.json`, `assignments.json`, logs, PID files, backups, real Spoolman URLs, credentials or private IP addresses.
