"""核对落盘 HTML 和资源的 SHA-256，识别未列入清单的文件及异常资源。"""
import argparse
import json
import os
import concurrent.futures
from collections import Counter
from pathlib import Path
from common import digest,write_json,jsonl

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    root = Path(parser.parse_args().project).resolve()
    resources = [json.loads(s) for s in (root/'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines()]
    pages = [json.loads(s) for s in (root/'data/manifests/pages.jsonl').read_text(encoding='utf-8').splitlines()]
    errors = []
    unknown = []
    total = 0
    def check_resource(row):
        data = (root /row['target']).read_bytes()
        error = None
        unrecognized = None
        if digest(data) != row['sha256']:
            error = {'target':row['target'],'kind':'resource_hash_mismatch'}
        if row['target'].endswith('.bin'):
            unrecognized = {'key':row['key'],'target':row['target'],'bytes':len(data),'header':repr(data[:120])}
        return len(data),error,unrecognized
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for size,error,unrecognized in pool.map(check_resource,resources):
            total += size
            if error:
                errors.append(error)
            if unrecognized:
                unknown.append(unrecognized)
    for row in pages:
        if digest((root /row['target']).read_bytes()) != row['html_sha256']:
            errors.append({'target':row['target'],'kind':'html_hash_mismatch'})
    tracked = {r['target'] for r in resources}
    candidates = [Path(folder,name).relative_to(root).as_posix() for folder,dirs,files in os.walk(root/'assets') for name in files]
    extra = [p for p in candidates if p not in tracked]
    summary = {'article_html_checked':len(pages),'resource_files_checked':len(resources),'resource_bytes':total,'hash_errors':len(errors),'unknown_resource_types':len(unknown),'untracked_assets':extra,'resource_origins':dict(Counter(r['repository'] for r in resources)),'resource_extensions':dict(Counter(Path(r['target']).suffix for r in resources))}
    write_json(root/'reports/integrity.json',summary)
    jsonl(root/'reports/integrity-errors.jsonl',errors)
    jsonl(root/'reports/unknown-resource-types.jsonl',unknown)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if errors:
        raise SystemExit(1)
