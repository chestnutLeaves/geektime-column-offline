"""只更新已生成页面的导航外壳；逐篇验证正文区域字节不变，并更新 HTML 校验值。"""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
from ui_common import active_section, render_page
from build_home import build_home
from public_paths import iter_public_files


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extract(document):
    """通过生成器边界切分页面，避免重新解析/序列化正文带来的格式改变。"""
    title = html.unescape(re.search(r'<title>(.*?)</title>', document, re.S).group(1)).removesuffix(' · 技术阅读库')
    if '<main class="reading-main" id="main-content">' in document:
        content = document.split('<main class="reading-main" id="main-content">', 1)[1].rsplit('<footer class="reading-footer">', 1)[0]
        match = re.search(r'<!-- chapter-navigation:start -->(.*?)<!-- chapter-navigation:end -->', document, re.S)
        navigation = match.group(1) if match else ''
    elif '</aside><main>' in document:
        navigation = document.split('<aside>', 1)[1].split('</aside>', 1)[0]
        content = document.split('</aside><main>', 1)[1].rsplit('<footer>', 1)[0]
    else:
        raise ValueError('无法识别页面外壳，停止覆盖')
    return title, content, navigation


def refresh(project):
    """先检查所有文章与既有清单一致，再逐页替换外壳，正文完全保持原样。"""
    root = project
    report_file = project / 'data/manifests/pages.jsonl'
    rows = [json.loads(line) for line in report_file.read_text(encoding='utf-8').splitlines() if line]
    article_rows = {row['target']: row for row in rows}
    # 浏览目录由 build_home 统一生成，不能按正文页的固定边界解析。
    excluded = {'index.html', 'courses/index.html', 'articles/index.html', 'geektime/index.html', 'relationships/index.html', 'downloads/index.html', 'course-sources.html'}
    # 只遍历对外发布的网页，避免把模板、缓存或开发备份当成文章。
    targets = [path for path in iter_public_files(root) if path.suffix == '.html' and path.relative_to(root).as_posix() not in excluded]
    for number, target in enumerate(targets, 1):
        data = target.read_bytes()
        relative = target.relative_to(root).as_posix()
        if relative in article_rows and digest(data) != article_rows[relative]['html_sha256']:
            raise ValueError('文章与最近清单不一致，请先确认已有修改：' + relative)
        extract(data.decode('utf-8'))
        if number % 1500 == 0:
            print(f'Preflight {number}/{len(targets)}', flush=True)
    backup = project / '.dev/navigation-before'
    backup.mkdir(parents=True, exist_ok=True)
    if not (backup / 'pages.jsonl').exists():
        shutil.copyfile(report_file, backup / 'pages.jsonl')
    audit = []
    unchanged = 0
    for number, target in enumerate(targets, 1):
        data = target.read_bytes()
        relative = target.relative_to(root).as_posix()
        title, content, navigation = extract(data.decode('utf-8'))
        navigation = navigation.replace('<strong>文章</strong>', '<strong>技术文章</strong>').replace('<strong>极客时间</strong>', '<strong>专栏合集</strong>').replace('<strong>恋爱必修课</strong>', '<strong>生活文章</strong>')
        updated = render_page(title, content, navigation, active_section(relative))
        if extract(updated)[1].encode('utf-8') != content.encode('utf-8'):
            raise ValueError('正文区域被改变，停止写入：' + relative)
        encoded = updated.encode('utf-8')
        if data != encoded:
            target.write_bytes(encoded)
        if relative in article_rows:
            article_rows[relative]['html_sha256'] = digest(encoded)
            unchanged += 1
        audit.append({'target': relative, 'before_sha256': digest(data), 'after_sha256': digest(encoded), 'content_sha256': digest(content.encode('utf-8')), 'content_bytes_preserved': True})
        if number % 1500 == 0:
            print(f'Layout refreshed {number}/{len(targets)}', flush=True)
    # 所有文章通过正文保护检查后，记录新的外壳哈希；原校验正文哈希不变。
    report_file.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8', newline='\n')
    build_home(project)
    (project / 'reports').mkdir(exist_ok=True)
    (project / 'reports/layout-changes.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in audit), encoding='utf-8', newline='\n')
    summary = {'updated_at': datetime.now(timezone.utc).isoformat(), 'layout_pages_checked': len(audit), 'article_bodies_preserved': unchanged, 'article_total': len(rows), 'body_bytes_changed': 0, 'technical_articles': 97, 'technical_collections': 9, 'life_articles': 18, 'docker_rebuilt': False, 'scope': '只修改导航外壳与目录页；原始正文、代码及资源未改变。'}
    if unchanged != len(rows):
        raise ValueError('正文保护校验未覆盖全部文章')
    (project / 'reports/layout-refresh.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    refresh(parser.parse_args().project.resolve())
