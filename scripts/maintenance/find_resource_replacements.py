"""根据图片文件标识在两个原始仓库中查找有效的同图副本。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import re
from pathlib import Path
from build_site import mime_extension
from common import *

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    root=Path(parser.parse_args().project).resolve()
    repos={'yvan':root / '.cache/upstream/Yvan0329-lianglianglee.git','xixi':root / '.cache/upstream/xixiwenxuanhe-learn-liangliang.git'}
    trees={n:tree(r) for n,r in repos.items()}
    readers={n:GitReader(r) for n,r in repos.items()}
    replacements={}
    checked=[]
    unknown_lines=(root/'reports/unknown-resource-types.jsonl').read_text(encoding='utf-8').splitlines()
    if not unknown_lines:
        for reader in readers.values():
            reader.close()
        raise SystemExit('没有新的未知资源；保留既有补图映射，不覆盖为空。')
    for line in unknown_lines:
        row=json.loads(line)
        base=row['key'].split('/')[-1]
        ids=re.findall(r'[0-9a-f]{32}',base)
        token=ids[0] if ids else base.split('?')[0].rsplit('.',1)[0]
        candidates=[]
        for name in repos:
            for path,sha in trees[name].items():
                if token not in path.split('/')[-1] or path.endswith(('.html','.md')):
                    continue
                data=readers[name].read(sha)
                ext=mime_extension(data,path)
                if ext in ('.png','.jpg','.gif','.webp','.svg'):
                    candidates.append({'repository':name,'path':path,'git_blob':sha,'sha256':digest(data),'size':len(data)})
        if candidates:
            replacements[row['key']]=candidates[0]
        checked.append({'key':row['key'],'valid_candidates':candidates})
    write_json(root/'data/provenance/resource-replacements.json',replacements)
    write_json(root/'reports/resource-replacement-search.json',checked)
    print(json.dumps({'found':len(replacements),'missing':[r['key'] for r in checked if not r['valid_candidates']],'replacements':replacements},ensure_ascii=False),flush=True)
    for reader in readers.values():
        reader.close()
