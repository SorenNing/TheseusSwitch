#!/usr/bin/env python3
"""Re-verify requested final packages independently of build/staging."""
import json
from pathlib import Path
import sys
from project import ROOT, CONFIG, sha256
from verify import verify

result, failed = [], False
out = ROOT/'evidence/final'; out.mkdir(parents=True, exist_ok=True)
for arch in (sys.argv[1:] or ['arm64e']):
    variant = CONFIG['variants'][arch]
    name = f'{CONFIG["package"]}_{CONFIG["version"]}_{variant["architecture"]}.deb'
    try:
        item = verify(ROOT/'dist'/name, arch, native=True)
        (ROOT/'dist'/(name+'.sha256')).write_text(item['sha256']+'  '+name+'\n')
        (ROOT/'dist'/(name+'.metadata.json')).write_text(json.dumps(item, indent=2)+'\n')
    except Exception as e:
        item = {'status': 'failed', 'package': name, 'variant': arch, 'error': str(e)}
        failed = True
    (out/(arch+'.json')).write_text(json.dumps(item, indent=2)+'\n')
    result.append({k: v for k, v in item.items() if k not in ('members', 'mach_o','control_members')})
(ROOT/'dist').mkdir(exist_ok=True)
(ROOT/'dist/SHA256SUMS').write_text(''.join(sha256(p)+'  '+p.name+'\n' for p in sorted((ROOT/'dist').glob('*.deb'))))
(out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
sys.exit(1 if failed else 0)
