"""下载指定的公开缺失图片，保留来源、HTTP 状态及字节校验值。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import ipaddress
import json
import urllib.request
import urllib.error
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from common import digest,write_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--url',required=True)
    args = parser.parse_args()
    root = Path(args.project).resolve()
    host = urlsplit(args.url).hostname
    if not args.url.startswith('https://') or not host:
        raise SystemExit('仅允许明确指定的公开 HTTPS 图片地址')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise SystemExit('不访问原始归档中残留的私有网络地址')
    file = root/'data/provenance/supplemental-resources.json'
    rows = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    row = {'url':args.url,'checked_at':datetime.now(timezone.utc).isoformat()}
    try:
        request = urllib.request.Request(args.url,headers={'User-Agent':'Mozilla/5.0 (compatible; personal-offline-verification/1.0)'})
        with urllib.request.urlopen(request,timeout=30) as response:
            data = response.read()
            if not data.startswith((b'\x89PNG',b'\xff\xd8\xff',b'GIF87a',b'GIF89a',b'RIFF')):
                raise ValueError('响应不是受支持的图片，拒绝写入网站')
            cache = root/'data/provenance/snapshots'/(digest(args.url.encode())+'.bin')
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
            row.update(status=response.status,cache=cache.relative_to(root).as_posix(),sha256=digest(data),size=len(data),content_type=response.headers.get('Content-Type'))
    except urllib.error.HTTPError as error:
        row.update(status=error.code,error=str(error))
    except Exception as error:
        row.update(status='error',error=str(error))
    rows[args.url] = row
    write_json(file,rows)
    print(json.dumps(row,ensure_ascii=False),flush=True)
