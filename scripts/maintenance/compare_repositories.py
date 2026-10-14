"""逐篇比较两个备份，并从成功读取的源站目录独立计算文章覆盖率。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from bs4 import BeautifulSoup
from common import *


def run(project):
    """目录核对仅使用真实源站响应，不将仓库种子列表当作源站证据。"""
    root = Path(project).resolve()
    source = root / '.cache/upstream'
    repos = {'yvan': source / 'Yvan0329-lianglianglee.git', 'xixi': source / 'xixiwenxuanhe-learn-liangliang.git'}
    trees = {}
    for name, repo in repos.items():
        trees[name] = {}
        for path, sha in tree(repo).items():
            if name == 'yvan':
                if not path.startswith('book/'):
                    continue
                path = path[5:]
            path = canonical(path)
            if path.split('/')[0] in CATEGORIES:
                trees[name][path] = sha
    articles = {name: {p for p in items if p.endswith('.md')} for name, items in trees.items()}
    common = sorted(articles['yvan'] & articles['xixi'])
    readers = {name: GitReader(repo) for name, repo in repos.items()}
    different = []
    valid = Counter()
    for number, path in enumerate(common, 1):
        bodies = {}
        codes = {}
        for name in repos:
            _, post = article_body(readers[name].read(trees[name][path]))
            valid[name] += post is not None
            bodies[name] = semantic_text(post)
            codes[name] = [p.get_text() for p in post.find_all('pre')] if post else []
        if bodies['yvan'] != bodies['xixi'] or codes['yvan'] != codes['xixi']:
            different.append({'path': path, 'same_text': bodies['yvan'] == bodies['xixi'], 'same_code_blocks': codes['yvan'] == codes['xixi']})
        if number % 1000 == 0:
            print(f'Compared {number}/{len(common)}', flush=True)
    for reader in readers.values():
        reader.close()
    live = {}
    for line in (root / 'data/provenance/source-pages.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        live[row['key']] = row
    catalogs = []
    paths = set()
    for key, row in live.items():
        if not key.endswith('index.html') or row.get('status') != 200:
            continue
        file = root / row['cache']
        soup = BeautifulSoup(file.read_text(encoding='utf-8'), 'html.parser')
        catalogs.append(key)
        for a in soup.find_all('a', href=True):
            url = urlsplit(urljoin(row['url'], a['href']))
            path = canonical(unquote(url.path).lstrip('/'))
            if url.netloc in HOSTS and path.split('/')[0] in CATEGORIES and path.endswith('.md'):
                paths.add(path)
    result = {'repository_article_counts': {name:len(paths) for name,paths in articles.items()},
              'shared_articles':len(common), 'shared_articles_with_body_or_code_difference':len(different),
              'valid_html_shared_articles':dict(valid),
              'yvan_only_articles':sorted(articles['yvan']-articles['xixi']),
              'xixi_only_articles':sorted(articles['xixi']-articles['yvan']),
              'successful_source_catalogs':len(catalogs), 'source_catalog_articles':len(paths),
              'source_catalog_missing_from_union':sorted(paths-(articles['yvan']|articles['xixi'])),
              'archive_articles_not_listed_in_source_catalogs':sorted((articles['yvan']|articles['xixi'])-paths),
              'source_catalog_category_counts':dict(Counter(p.split('/')[0] for p in paths)),
              'source_body_equivalence_fully_verified':False}
    write_json(root / 'reports/repository-comparison.json', result)
    jsonl(root / 'reports/repository-body-differences.jsonl',different)
    write_json(root / 'reports/source-catalog-evidence.json', {'catalog_pages':sorted(catalogs),'article_paths':sorted(paths)})
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    run(parser.parse_args().project)
