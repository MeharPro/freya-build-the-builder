#!/usr/bin/env bash
# Inspect staged blobs. Report paths only; never print matching credentials.
set -eu
python3 - <<'PYCODE'
import os,re,shlex,subprocess,sys
from pathlib import Path
secrets=[]
for name in ('FREYA_API_KEY','FREYA_BANK_TEAM_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY'):
    if os.environ.get(name):secrets.append(os.environ[name].encode())
if Path('env.sh').exists():
    for line in Path('env.sh').read_text().splitlines():
        try:
            words=shlex.split(line)
            if words and words[0]=='export':words=words[1:]
            for word in words:
                k,sep,v=word.partition('=')
                if sep and k in ('FREYA_API_KEY','FREYA_BANK_TEAM_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY') and v and 'your_key' not in v and 'pick-any-secret' not in v:secrets.append(v.encode())
        except ValueError:pass
paths=subprocess.check_output(['git','ls-files','-z']).split(b'\0')
bad=[]
for raw in paths:
    if not raw:continue
    path=os.fsdecode(raw)
    blob=subprocess.check_output(['git','show',':'+path])
    hits=re.findall(rb'(?<![A-Za-z0-9_])(?:fak_[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{16,})',blob)
    if any(b'your_key' not in h for h in hits) or any(s in blob for s in secrets):bad.append(path)
if bad:
    print('Remove credentials from these staged paths:',file=sys.stderr)
    for p in bad:print(p,file=sys.stderr)
    sys.exit(1)
print('check_secrets: no credentials found in staged files')
PYCODE
