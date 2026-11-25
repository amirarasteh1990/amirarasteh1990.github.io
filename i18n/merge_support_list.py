# -*- coding: utf-8 -*-
"""Merge i18n/support_list_2026-11-25.json (Thanks page Financial support list, Support page
opt-in line) into every i18n/<code>.json. Each msgid must be in source.json (run
build_i18n.py extract first). Keeps each dictionary's own JSON layout. ASCII output.

    python i18n/merge_support_list.py [--apply]     then: build_i18n.py build, sync_head.py
"""
import io, json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
new = json.load(io.open(os.path.join(D, 'support_list_2026-11-25.json'), encoding='utf-8'))
new.pop('_note', None)
src = json.load(io.open(os.path.join(D, 'source.json'), encoding='utf-8'))['strings']
miss = [k for k in new if k not in src]
for k in miss:
    print('NOT IN source.json:', k.encode('ascii', 'replace').decode())
if miss:
    sys.exit(1)
codes = sorted({c for v in new.values() for c in v})
for c in codes:
    p = os.path.join(D, c + '.json')
    raw = io.open(p, encoding='utf-8').read()
    d = json.loads(raw)
    indent = 1 if raw.startswith('{\n "') else (2 if raw.startswith('{\n  "') else None)
    added = 0
    for k, v in new.items():
        if c in v and d.get(k) != v[c]:
            d[k] = v[c]
            added += 1
    if '--apply' in sys.argv and added:
        io.open(p, 'w', encoding='utf-8', newline='\n').write(json.dumps(d, ensure_ascii=False, indent=indent) + '\n')
    print(c, 'added', added)
print('WRITTEN' if '--apply' in sys.argv else '(check only)')
