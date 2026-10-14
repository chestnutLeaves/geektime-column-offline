"""为正文有差异的备份生成可阅读的文本差异文件。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import difflib
import json
from pathlib import Path
from common import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    root = Path(parser.parse_args().project).resolve()
    repos = {'yvan':root / '.cache/upstream/Yvan0329-lianglianglee.git','xixi':root / '.cache/upstream/xixiwenxuanhe-learn-liangliang.git'}
    trees = {n:tree(r) for n,r in repos.items()}
    readers = {n:GitReader(r) for n,r in repos.items()}
    output = []
    findings = []
    for line in (root/'reports/repository-body-differences.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        key = row['path']
        blocks = {}
        texts = {}
        for name in repos:
            original = 'book/'+key if name == 'yvan' else key+'.html'
            _, post = article_body(readers[name].read(trees[name][original]))
            blocks[name] = post.get_text().splitlines(keepends=True)
            texts[name] = semantic_text(post)
        delta = ''.join(difflib.unified_diff(blocks['yvan'],blocks['xixi'],fromfile='Yvan: '+key,tofile='xixi: '+key,n=2))
        output.append(delta)
        suffix_only = texts['yvan'] == texts['xixi'].replace('.md.html','.md')
        findings.append({'path':key,'difference':'md_suffix_replaced_in_body' if suffix_only else 'other_text_difference','selected':'yvan'})
    (root/'reports/repository-body-differences.diff').write_text('\n'.join(output),encoding='utf-8')
    write_json(root/'reports/difference-analysis.json',{'suffix_replacement_articles':sum(r['difference']=='md_suffix_replaced_in_body' for r in findings),'other_articles':[r for r in findings if r['difference']!='md_suffix_replaced_in_body'],'details':findings})
    print(json.dumps({'suffix_replacement_articles':sum(r['difference']=='md_suffix_replaced_in_body' for r in findings),'other_articles':[r for r in findings if r['difference']!='md_suffix_replaced_in_body']},ensure_ascii=False),flush=True)
    for reader in readers.values():
        reader.close()
