"""低频尝试恢复审核清单中的坏图，遇到访问限制立即结束本批次。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from audit_source import Fetcher
from build_site import mime_extension
from common import digest,write_json

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    root=Path(parser.parse_args().project).resolve()
    replacements=json.loads((root/'data/provenance/resource-replacements.json').read_text(encoding='utf-8'))
    rows={r['key']:r for r in (json.loads(s) for s in (root/'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines())}
    file=root/'data/provenance/supplemental-resources.json'
    results=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    fetcher=Fetcher(3)
    for key,row in rows.items():
        if not row['target'].endswith('.bin') or key in replacements:
            continue
        url=row['source_url']
        host=urlsplit(url).hostname
        if host not in ('learn.lianglianglee.com','p1-juejin.byteimg.com') or not url.startswith('https://'):
            continue
        data,status=fetcher.fetch(url)
        status.update(url=url,checked_at=datetime.now(timezone.utc).isoformat(),key=key)
        if data is not None:
            extension=mime_extension(data,url)
            if extension == '.bin':
                status.update(status='invalid_image',response_http_status=status['status'],response_sha256=digest(data))
            else:
                target=root/'data/provenance/snapshots'/(digest(url.encode())+'.bin')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                status.update(cache=target.relative_to(root).as_posix(),sha256=digest(data),size=len(data))
        results[url]=status
        write_json(file,results)
        print(json.dumps({'key':key,'status':status['status']},ensure_ascii=False),flush=True)
        if status['status'] in (403,429):
            print('源站访问受限，停止本批次；未执行的请求保持待核验状态。',flush=True)
            break
