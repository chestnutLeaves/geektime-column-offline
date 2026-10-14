"""重建引用已确认坏图的文章，并清理该批生成的错误页资源。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import subprocess
import sys
from pathlib import Path
from common import write_json

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    root=Path(parser.parse_args().project).resolve()
    unknown=[json.loads(s) for s in (root/'reports/unknown-resource-types.jsonl').read_text(encoding='utf-8').splitlines()]
    if not unknown:
        raise SystemExit('当前清单没有未知资源类型，不需要再次修复。')
    patterns=root/'data/provenance/invalid-resource-targets.txt'
    patterns.write_text('\n'.join(r['target'] for r in unknown)+'\n',encoding='utf-8')
    raw=subprocess.check_output(['rg','--null','-l','-F','-f',str(patterns),'-g','*.html',str(root)])
    affected={Path(s.decode('utf-8')).resolve() for s in raw.split(b'\0') if s}
    pages=[json.loads(s) for s in (root/'data/manifests/pages.jsonl').read_text(encoding='utf-8').splitlines()]
    selected=[r['source_path'] for r in pages if (root /r['target']).resolve() in affected]
    write_json(root/'data/provenance/resource-repair-pages.json',selected)
    command=[sys.executable,str(root/'scripts/maintenance/build_site.py'),'--project',str(root)]
    for key in selected:
        command.extend(['--only',key])
    if not selected:
        raise SystemExit('没有找到对应文章，停止操作。')
    subprocess.run(command,check=True)
    tracked={json.loads(s)['target'] for s in (root/'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines()}
    removed=[]
    for row in unknown:
        path=(root /row['target']).resolve()
        if path.is_relative_to((root/'assets').resolve()) and row['target'] not in tracked and path.is_file():
            path.unlink()
            removed.append(row['target'])
    write_json(root/'reports/resource-repair-run.json',{'rebuilt_articles':selected,'removed_generated_error_files':removed})
    print(json.dumps({'rebuilt_articles':len(selected),'removed_generated_error_files':len(removed)},ensure_ascii=False),flush=True)
