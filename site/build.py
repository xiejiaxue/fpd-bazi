#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把引擎与规则数据复制进 site/public，保证网页运行的是与测试同一份代码。

用法：python3 site/build.py   （之后在 site/ 下 npx wrangler deploy --domain fpd.xiejiaxue.com）
"""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = Path(__file__).resolve().parent / 'public'
ENGINE_FILES = ['bazi_engine.py', 'rules.json', 'terms_1900_2100.json']
DOC_FILES = {'verification_report.md': 'verification_report.md', '子平八字_AI公式书_V1.0.md': 'formula_book.md'}


def main():
    r = subprocess.run([sys.executable, '-m', 'unittest', 'test_bazi_engine'], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('测试未通过，拒绝构建：\n' + r.stderr[-2000:])
    (PUB / 'engine').mkdir(parents=True, exist_ok=True)
    (PUB / 'docs').mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    for f in ENGINE_FILES:
        shutil.copyfile(ROOT / f, PUB / 'engine' / f)
        digest.update((ROOT / f).read_bytes())
    for src, dst in DOC_FILES.items():
        shutil.copyfile(ROOT / src, PUB / 'docs' / dst)
    rules = json.loads((ROOT / 'rules.json').read_text(encoding='utf-8'))
    engine_version = next(l.split('"')[1] for l in (ROOT / 'bazi_engine.py').read_text(encoding='utf-8').splitlines() if l.startswith('ENGINE_VERSION'))
    manifest = {'engine_version': engine_version, 'rules_version': rules['schema_version'],
                'sha256': digest.hexdigest()[:16], 'built_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'files': ENGINE_FILES, 'tests': r.stderr.strip().splitlines()[-3].strip()}
    (PUB / 'engine' / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
