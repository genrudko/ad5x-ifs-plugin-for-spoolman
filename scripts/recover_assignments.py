#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

target=Path(sys.argv[1])
legacy=Path(sys.argv[2])
out=target/'assignments.json'

def load(path):
    try:
        raw=json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(raw,dict): return None
    result={}; seen=set(); count=0
    for n in range(1,5):
        v=raw.get(str(n))
        if v in (None,'',0,'0'):
            result[str(n)]=None; continue
        if isinstance(v,bool): return None
        try: v=int(v)
        except (TypeError,ValueError): return None
        if v<=0 or v in seen: return None
        seen.add(v); count+=1; result[str(n)]=v
    return result,count

current=load(out) if out.exists() else None
if current and current[1]>0:
    print(f'IFS assignments preserved: {current[1]}/4')
    raise SystemExit(0)

candidates=[]
def add(path):
    if path.exists() and path.resolve()!=out.resolve():
        try: m=path.stat().st_mtime
        except OSError: m=0
        candidates.append((m,path))

add(legacy/'assignments.json')
for path in legacy.parent.glob(legacy.name+'.pre-git-*/assignments.json'): add(path)
for path in target.parent.glob(target.name+'.pre-git-*/assignments.json'): add(path)
for path in (target/'backups').glob('update_*/assignments.json'): add(path)
# Historical Z-Mod experiments used closely related plugin directory names.
plugins=target.parent/'plugins'
if plugins.is_dir():
    for path in plugins.glob('*ifs*spoolman*.pre-git-*/assignments.json'): add(path)

for _,path in sorted(candidates,key=lambda item:item[0],reverse=True):
    parsed=load(path)
    if not parsed or parsed[1]==0: continue
    data,count=parsed
    target.mkdir(parents=True,exist_ok=True)
    tmp=out.with_name(out.name+'.recover.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,out)
    print(f'IFS assignments recovered: {count}/4 from {path}')
    raise SystemExit(0)

if current is None and out.exists():
    print('WARNING: current assignments.json is invalid; no valid legacy mapping found',file=sys.stderr)
else:
    print('IFS assignments recovery: no previous non-empty mapping found')
