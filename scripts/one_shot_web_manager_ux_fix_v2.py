#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/one_shot_web_manager_ux_fix.py')
code = path.read_text(encoding='utf-8')
old = '''needle = '            outlined\\n            :disabled="!spoolmanUrl"\\n'
if vue.count(needle) != 2:
    raise SystemExit(f"spoolman button baseline count={vue.count(needle)}")
vue = vue.replace(needle, '            outlined\\n            class="ifs-spoolman-link"\\n            :disabled="!spoolmanUrl"\\n', 2)
'''
new = '''needle = '            :disabled="!spoolmanUrl"\\n'
if vue.count(needle) != 2:
    raise SystemExit(f"spoolman button baseline count={vue.count(needle)}")
vue = vue.replace(needle, '            class="ifs-spoolman-link"\\n' + needle, 2)
'''
if old not in code:
    raise SystemExit('expected v1 button patch block not found')
code = code.replace(old, new, 1)
exec(compile(code, str(path), 'exec'), {'__name__': '__main__', '__file__': str(path)})
