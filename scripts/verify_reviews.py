"""校验点评覆盖范围、证据正文与静态页面关联；不访问网络、不修改文件。"""
import argparse
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

RECOMMENDATIONS = {'recommended', 'selective', 'reference', 'uncertain'}
CURRENCIES = {'stable', 'mixed', 'dated', 'contextual', 'unknown'}


def local_file(project, value):
    """仅接受站内内容 HTML，拒绝目录穿越、查询参数和协议相对路径。"""
    if not isinstance(value, str) or not value.startswith('/') or value.startswith('//') or '\\' in value:
        raise ValueError(f'非法本地路径：{value}')
    parsed = urlsplit(value)
    parts = PurePosixPath(parsed.path).parts
    if parsed.query or parsed.fragment or '..' in parts or len(parts) < 3 or parts[1] not in {'courses', 'articles', 'geektime'} or not value.endswith('.html'):
        raise ValueError(f'非法内容路径：{value}')
    target = (project / value.lstrip('/')).resolve()
    if not target.is_relative_to(project.resolve()) or not target.is_file():
        raise ValueError(f'内容文件不存在或越界：{value}')
    return target


class ReviewKeys(HTMLParser):
    """只读取渲染页的点评关联键，不执行其中脚本。"""
    def __init__(self):
        super().__init__()
        self.keys = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-review-key' in attrs:
            self.keys.append(attrs['data-review-key'])


def validate_document(project, data, kind, expected):
    """使漏评、错配、过期正文证据与损坏字段在发布前明确报错。"""
    if data.get('schema_version') != 1 or data.get('kind') != kind:
        raise ValueError('点评版本或分类错误')
    date.fromisoformat(data['reviewed_at'])
    if not data.get('methodology') or not data.get('reviewer'):
        raise ValueError('缺少点评范围或署名')
    references = data['references']
    for reference in references.values():
        url = urlsplit(reference['url'])
        if url.scheme != 'https' or not url.netloc or url.username or url.password or not reference['title']:
            raise ValueError('官方资料链接格式错误')
        date.fromisoformat(reference['checked_at'])
    seen = set()
    for entry in data['entries']:
        path = entry['path']
        if path in seen or path not in expected:
            raise ValueError(f'重复或多余点评：{path}')
        seen.add(path)
        if entry['title'] != expected[path]:
            raise ValueError(f'标题不匹配：{path}')
        local_file(project, path)
        if entry['recommendation'] not in RECOMMENDATIONS or entry['currency'] not in CURRENCIES:
            raise ValueError(f'点评等级错误：{path}')
        for key in ('summary', 'currency_note', 'reading_advice'):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError(f'点评字段为空：{path} {key}')
        if not isinstance(entry['reference_ids'], list) or any(key not in references for key in entry['reference_ids']):
            raise ValueError(f'资料引用不存在：{path}')
        if not entry['evidence']:
            raise ValueError(f'缺少正文依据：{path}')
        for evidence in entry['evidence']:
            if kind == 'courses' and PurePosixPath(evidence['path']).parent != PurePosixPath(path).parent:
                raise ValueError(f'证据不属于当前专栏：{path}')
            if kind == 'articles' and evidence['path'] != path:
                raise ValueError(f'证据不属于当前文章：{path}')
            document = local_file(project, evidence['path']).read_text(encoding='utf-8')
            body = document.split('<main class="reading-main" id="main-content">', 1)[1].split('<footer class="reading-footer">', 1)[0]
            if hashlib.sha256(body.encode()).hexdigest() != evidence['sha256']:
                raise ValueError(f'证据正文已变化，需复核点评：{evidence["path"]}')
    if seen != set(expected):
        raise ValueError(f'漏评 {len(set(expected) - seen)} 项')
    return len(seen)


def verify(project):
    """从内容清单计算应有条目，并核对两个目录及旧文章入口。"""
    project = Path(project)
    rows = [json.loads(line) for line in (project / 'data/manifests/pages.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    expected = {'courses': {}, 'articles': {}}
    for row in rows:
        if row['source_path'].startswith('专栏/'):
            expected['courses']['/' + str(PurePosixPath(row['target']).parent / 'index.html')] = PurePosixPath(row['source_path']).parent.name
        elif row['source_path'].startswith(('文章/', '极客时间/')):
            expected['articles']['/' + row['target']] = PurePosixPath(row['source_path']).stem
    for kind in expected:
        data = json.loads((project / f'static/reviews/{kind}.json').read_text(encoding='utf-8'))
        count = validate_document(project, data, kind, expected[kind])
        pages = [f'{kind}/index.html'] + (['geektime/index.html'] if kind == 'articles' else [])
        for page in pages:
            parser = ReviewKeys()
            parser.feed((project / page).read_text(encoding='utf-8'))
            if len(parser.keys) != count or set(parser.keys) != set(expected[kind]):
                raise ValueError(f'页面点评关联缺失或重复：{page}')
        print(f'{kind}: {count} reviews; coverage, references, body evidence and page keys OK')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    verify(parser.parse_args().project)
