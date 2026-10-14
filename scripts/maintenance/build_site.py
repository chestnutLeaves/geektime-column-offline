"""合并两个 Git 备份，使用已校验源站正文生成纯 HTML 离线阅读站。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import html
import json
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
from bs4 import BeautifulSoup, NavigableString
from common import *
from build_home import build_home
from ui_common import render_page, active_section


def page_html(title, body, navigation='', origin=None):
    """使用全站共用导航包装原文，阅读主题直接维护在静态 CSS 文件中。"""
    source = f'<p class="origin">原始页面：<a href="{html.escape(origin)}" rel="noreferrer">源站链接</a></p>' if origin else ''
    return render_page(title, source + body, navigation, active_section(origin or title))


def mime_extension(data, original):
    """根据真实文件头选择扩展名，避免原资源名称中的查询参数进入文件名。"""
    if data.startswith(b'\x89PNG'):
        return '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return '.gif'
    if data.startswith(b'%PDF'):
        return '.pdf'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    ext = Path(urlsplit(original).path).suffix.lower()
    if ext in {'.svg', '.css', '.js', '.woff', '.woff2', '.ttf', '.mp3', '.mp4', '.webm', '.ico', '.zip'}:
        return ext
    if b'<svg' in data[:500]:
        return '.svg'
    return '.bin'

def run(args):
    project = Path(args.project).resolve()
    site = project
    reports = project / 'reports'
    manifests = project / 'data/manifests'
    manifests.mkdir(parents=True, exist_ok=True)
    sources = project / '.cache/upstream'
    site.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    (site / 'static').mkdir(exist_ok=True)
    repos = {'yvan': sources / 'Yvan0329-lianglianglee.git', 'xixi': sources / 'xixiwenxuanhe-learn-liangliang.git'}
    readers = {name: GitReader(repo) for name, repo in repos.items()}
    entries = {}
    provenance = {}
    metadata = {}
    for name, repo in repos.items():
        metadata[name] = {'url': subprocess.check_output(['git', '--git-dir', str(repo), 'remote', 'get-url', 'origin'], text=True).strip(), 'commit': subprocess.check_output(['git', '--git-dir', str(repo), 'rev-parse', 'HEAD'], text=True).strip()}
        for original, sha in tree(repo).items():
            if name == 'yvan':
                if not original.startswith('book/'):
                    continue
                key = original[5:]
            else:
                key = canonical(original)
                if key.split('/')[0] not in CATEGORIES and not key.startswith('static/'):
                    continue
            if '.DS_Store' in key or key.startswith('.'):
                continue
            provenance.setdefault(key, {})[name] = sha
            entries.setdefault(key, {'repo': name, 'sha': sha, 'original': original})
    page_keys = sorted(k for k in entries if k.endswith('.md') and k.split('/')[0] in CATEGORIES)
    live = {}
    source_report = project / 'data/provenance/source-pages.jsonl'
    if source_report.exists():
        for line in source_report.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            live[row['key']] = row
            if row['key'].endswith('.md') and row['key'].split('/')[0] in CATEGORIES and row.get('status') == 200 and row['key'] not in page_keys:
                page_keys.append(row['key'])
    page_keys.sort()
    targets = {k: output_page(k) for k in page_keys}
    # 提前检查规范化后的路径碰撞，防止静默覆盖章节。
    seen = {}
    for key, target in list(targets.items()):
        folded = target.casefold()
        if folded in seen:
            target = target[:-5] + '-' + digest(key.encode())[:8] + '.html'
            targets[key] = target
        seen[target.casefold()] = key
    groups = defaultdict(list)
    for key in page_keys:
        group = key.rsplit('/', 1)[0]
        groups[group].append(key)
    for group in groups:
        targets[group] = output_page(group + '/index.html')
        targets[group + '/index.html'] = targets[group]
    for category in CATEGORIES:
        targets[category] = CATEGORIES[category] + '/index.html'
        targets[category + '/index.html'] = targets[category]
    targets[''] = targets['index.html'] = 'index.html'
    by_basename = defaultdict(list)
    for key in entries:
        by_basename[key.rsplit('/', 1)[-1]].append(key)
    asset_rows = {}
    issues = []
    page_rows = []
    # 定向修复只重建指定文章，沿用其他页面的既有校验记录。
    selected_pages = set(args.only or [])
    extra_file = project / 'data/provenance/supplemental-resources.json'
    supplemental = json.loads(extra_file.read_text(encoding='utf-8')) if extra_file.exists() else {}
    replacements_file = project / 'data/provenance/resource-replacements.json'
    replacements = json.loads(replacements_file.read_text(encoding='utf-8')) if replacements_file.exists() else {}
    if selected_pages:
        if not selected_pages <= set(page_keys):
            raise ValueError('指定的文章不在文件清单中')
        asset_rows = {r['key']:r for r in (json.loads(s) for s in (manifests / 'resources.jsonl').read_text(encoding='utf-8').splitlines())}
        asset_rows = {k:r for k,r in asset_rows.items() if not r['target'].endswith('.bin')}
        issues = [r for r in (json.loads(s) for s in (manifests / 'issues.jsonl').read_text(encoding='utf-8').splitlines()) if r.get('page') not in selected_pages]
        page_rows = [r for r in (json.loads(s) for s in (manifests / 'pages.jsonl').read_text(encoding='utf-8').splitlines()) if r['source_path'] not in selected_pages]

    def prepare_html(raw, key):
        """修复已确认的原始标签转义错误，防止 iframe 吞掉后半篇文章。"""
        if key == '专栏/Web漏洞挖掘实战/30 HTTP Header安全标志：协议级别的安全支持.md':
            before = '可在 <frame>、<iframe>、<embed> 或者 <object> 中展现设置的内容。'.encode()
            after = '可在 &lt;frame&gt;、&lt;iframe&gt;、&lt;embed&gt; 或者 &lt;object&gt; 中展现设置的内容。'.encode()
            if before in raw:
                issues.append({'kind':'repaired_source_markup','page':key,'detail':'将说明文字中的四个 HTML 标签转义为字面文本，恢复后半篇正文与图片。'})
                raw = raw.replace(before,after)
        return raw

    def asset(key, url):
        if key in asset_rows:
            return asset_rows[key]['target']
        entry = entries[key]
        data = readers[entry['repo']].read(entry['sha'])
        extension = mime_extension(data, key)
        replacement = replacements.get(key)
        if extension == '.bin' and replacement:
            entry = {'repo':replacement['repository'],'sha':replacement['git_blob'],'original':replacement['path']}
            data = readers[entry['repo']].read(entry['sha'])
            if digest(data) != replacement['sha256']:
                raise ValueError('补图 Git 对象与审核清单不符: '+key)
            extension = mime_extension(data,entry['original'])
        if extension == '.bin':
            return None
        target = ('downloads/' if extension == '.pdf' else 'assets/') + digest(key.encode())[:24] + extension
        output = site / target
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        asset_rows[key] = {'key': key, 'target': target, 'source_url': url, 'sha256': digest(data), 'size': len(data), 'repository': entry['repo'], 'git_blob': entry['sha'], 'original_git_path':entry['original']}
        return target

    def resolve(value, source, kind):
        """重写文章、图片和附件引用，保留普通外部参考链接。"""
        if not value or value.startswith(('#', 'data:', 'mailto:', 'tel:', 'javascript:')):
            return value
        try:
            absolute = urljoin(source_url(source), value)
            split = urlsplit(absolute)
        except ValueError:
            # 原文自动识别链接时可能混入中文说明；保留文字并记录原始值。
            issues.append({'kind': 'malformed_original_url', 'page': source, 'url': value})
            return '#'
        internal = split.netloc in HOSTS
        key = canonical(unquote(split.path).lstrip('/')).rstrip('/')
        if internal and key in targets:
            return '/' + quote(targets[key], safe='/') + ('#' + split.fragment if split.fragment else '')
        candidates = [key + ('?' + split.query if split.query else '') + ('#' + split.fragment if split.fragment else ''), key + ('?' + split.query if split.query else ''), key]
        match = next((c for c in candidates if c in entries), None) if internal else None
        if match is None and kind != 'link':
            base = unquote(split.path).rsplit('/', 1)[-1]
            names = [base + ('?' + split.query if split.query else '') + ('#' + split.fragment if split.fragment else ''), base]
            for name in names:
                local = [source.rsplit('/',1)[0]+'/assets/'+name,source.split('/')[0]+'/assets/'+name]
                match = next((p for p in local if p in entries),None)
                same = by_basename.get(name, [])
                if match is None and len(same) == 1:
                    match = same[0]
                if match:
                    break
        if match and not match.endswith(('.md', 'index.html')):
            target = asset(match, absolute)
            if target:
                return '/' + quote(target, safe='/')
            issues.append({'kind':'invalid_archived_resource','page':source,'key':match,'url':absolute})
        if kind == 'link':
            if internal and not key.startswith(('cdn-cgi/', 'assets/捐赠')):
                issues.append({'kind': 'unresolved_internal_link', 'page': source, 'url': absolute})
            return absolute
        cached = supplemental.get(absolute)
        if cached and cached.get('status') == 200:
            data = (project / cached['cache']).read_bytes()
            if digest(data) != cached['sha256']:
                raise ValueError('补充资源校验值不匹配: '+absolute)
            target = 'assets/'+digest(absolute.encode())[:24]+mime_extension(data,absolute)
            (site/target).write_bytes(data)
            asset_rows[absolute] = {'key':absolute,'target':target,'source_url':absolute,'sha256':digest(data),'size':len(data),'repository':'downloaded_original_resource','git_blob':None}
            return '/'+target
        # 缺图使用明确标注的本地占位图，避免离线时静默显示损坏图标。
        target = 'assets/missing-'+digest(absolute.encode())[:24]+'.svg'
        placeholder = '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="130" viewBox="0 0 720 130"><rect x="1" y="1" width="718" height="128" rx="10" fill="#fff8ef" stroke="#d7af78"/><text x="28" y="52" font-size="20" fill="#80542b">原始图片未能获取</text><text x="28" y="88" font-size="15" fill="#80542b">原链接和失败记录已保留，请查看项目校验报告。</text></svg>'.encode()
        (site/target).write_bytes(placeholder)
        asset_rows[absolute] = {'key':absolute,'target':target,'source_url':absolute,'sha256':digest(placeholder),'size':len(placeholder),'repository':'missing_placeholder','git_blob':None}
        issues.append({'kind': 'missing_original_resource', 'page': source, 'url': absolute, 'placeholder':target})
        return '/'+target

    def navigation(group, current=None):
        links = ['<p><a href="/">← 全部课程</a></p>', '<strong>' + html.escape(group.split('/')[-1]) + '</strong><ul>']
        for key in groups[group]:
            label = Path(key).name[:-3]
            active = ' class="active"' if key == current else ''
            links.append('<li><a' + active + ' href="/' + quote(targets[key], safe='/') + '">' + html.escape(label) + '</a></li>')
        return ''.join(links) + '</ul>'

    for number, key in enumerate(page_keys, 1):
        if selected_pages and key not in selected_pages:
            continue
        entry = entries.get(key)
        archive_data = readers[entry['repo']].read(entry['sha']) if entry else b''
        archive_data = prepare_html(archive_data,key)
        original_soup, original_post = article_body(archive_data)
        verified = live.get(key, {})
        live_file = project / verified.get('cache', 'not-present')
        data = archive_data
        selected = entry['repo'] if entry else 'unavailable'
        if verified.get('status') == 200 and live_file.is_file():
            data = prepare_html(live_file.read_bytes(),key)
            selected = 'live_source'
        soup, post = article_body(data) if selected == 'live_source' else (original_soup, original_post)
        if post is None:
            issues.append({'kind': 'invalid_article', 'page': key})
            post = BeautifulSoup('<div class="book-post"><p class="missing">正文无法解析，请查看项目校验报告。</p></div>', 'html.parser').div
        # 这些脚本均位于教学正文中，作为字面示例展示，避免执行或丢失示例代码。
        for node in post.find_all('script'):
            issues.append({'kind':'escaped_example_script','page':key,'example':str(node)})
            node.replace_with(NavigableString(str(node)))
        baseline = semantic_text(post)
        original_code = [node.get_text() for node in post.find_all('pre')]
        # 只移除执行性节点；正文、代码、作者署名与引用文字保留。
        for node in post.find_all(['iframe']):
            issues.append({'kind': 'removed_executable_node', 'page': key, 'tag': node.name})
            node.decompose()
        for node in post.find_all(True):
            for attr in list(node.attrs):
                if attr.lower().startswith('on'):
                    del node.attrs[attr]
            for attr in ('src', 'poster'):
                if node.get(attr):
                    node[attr] = resolve(node[attr], key, 'resource')
            if node.get('href'):
                node['href'] = resolve(node['href'], key, 'link')
            if node.get('srcset'):
                parts = []
                for item in node['srcset'].split(','):
                    bits = item.strip().split()
                    if bits:
                        bits[0] = resolve(bits[0], key, 'resource')
                        parts.append(' '.join(bits))
                node['srcset'] = ', '.join(parts)
            if node.get('style') and 'url(' in node['style']:
                node['style'] = re.sub(r'url\([\"\']?([^\)\"\']+)[\"\']?\)', lambda m: 'url("' + resolve(m.group(1), key, 'resource') + '")', node['style'])
        group = key.rsplit('/', 1)[0]
        title = Path(key).name[:-3]
        document = page_html(title, str(post), navigation(group, key), source_url(key))
        target = site / targets[key]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding='utf-8', newline='\n')
        _, output_post = article_body(document)
        output_text = semantic_text(output_post)
        body_equal = baseline == output_text
        code_equal = original_code == [node.get_text() for node in output_post.find_all('pre')]
        if not body_equal:
            issues.append({'kind': 'body_changed_during_conversion', 'page': key})
        if not code_equal:
            issues.append({'kind': 'code_block_changed_during_conversion', 'page': key})
        page_rows.append({'source_path': key, 'source_url': source_url(key), 'target': targets[key], 'selected_source': selected, 'source_http_status': verified.get('status', 'not_checked'), 'archive_matches_live_text': semantic_text(original_post) == baseline if selected == 'live_source' else None, 'conversion_preserves_text': body_equal, 'code_blocks_preserved': code_equal, 'body_sha256': digest(output_text.encode()), 'html_sha256': digest(document.encode()), 'repositories': provenance.get(key, {})})
        if number % 100 == 0:
            write_json(reports / 'build-progress.json', {'completed': number, 'total': len(page_keys), 'resources': len(asset_rows)})
            print(f'pages {number}/{len(page_keys)}, assets {len(asset_rows)}', flush=True)
    # 即使首页未提供 PDF 导航，也保留仓库中的全部 PDF 附件。
    pdf_links = []
    for key in sorted(entries):
        if key.startswith('PDF/') and key.endswith('.pdf'):
            target = asset(key, source_url(key))
            pdf_links.append('<li><a href="/' + target + '">' + html.escape(Path(key).name) + '</a></li>')
    for group, keys in groups.items():
        body = '<h1>' + html.escape(group.split('/')[-1]) + '</h1><p class="muted">共 ' + str(len(keys)) + ' 篇文章</p><ul>'
        body += ''.join('<li><a href="/' + quote(targets[k], safe='/') + '">' + html.escape(Path(k).name[:-3]) + '</a></li>' for k in keys) + '</ul>'
        target = site / targets[group]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html(group, body, navigation(group)), encoding='utf-8')
    course_groups = sorted(g for g in groups if g.startswith('专栏/'))
    cards = ''.join('<section class="card" data-title="' + html.escape(g.split('/')[-1].lower()) + '"><h2><a href="/' + quote(targets[g], safe='/') + '">' + html.escape(g.split('/')[-1]) + '</a></h2><span class="muted">' + str(len(groups[g])) + ' 篇文章</span></section>' for g in course_groups)
    (site / 'static/search.js').write_text('/* 本地筛选课程名称，不上传搜索内容。 */\ndocument.querySelector(".search")?.addEventListener("input",function(){const q=this.value.trim().toLowerCase();document.querySelectorAll(".card").forEach(e=>e.hidden=!e.dataset.title.includes(q));});', encoding='utf-8')
    (site / 'courses').mkdir(exist_ok=True)
    (site / 'courses/index.html').write_text(page_html('全部专栏', '<h1>全部专栏</h1><div class="cards">' + cards + '</div>', '<a href="/">首页</a>'), encoding='utf-8')
    (site / 'downloads').mkdir(exist_ok=True)
    (site / 'downloads/index.html').write_text(page_html('PDF 下载', '<h1>PDF 下载</h1><ul>' + ''.join(pdf_links) + '</ul>', '<a href="/">首页</a>'), encoding='utf-8')
    verified_count = sum(p['selected_source'] == 'live_source' for p in page_rows)
    about = '<h1>关于与校验说明</h1><p>本项目整理公开归档页面，保留正文与原作者信息。全部文章使用 HTML，图片与附件按本地路径引用。</p><p>本次构建包含 ' + str(len(page_rows)) + ' 篇文章；其中 ' + str(verified_count) + ' 篇使用成功读取的源站正文。目录或资源校验失败不等同于内容不存在，也不会被计为校验成功。</p><p>详细逐条记录位于项目 reports/ 与 data/provenance/ 目录。源站访问限制、原始死链、外部资源和正文差异均单独记录。</p><p>原站：<a href="https://learn.lianglianglee.com/">learn.lianglianglee.com</a></p>'
    (site / 'about.html').write_text(page_html('关于', about, '<a href="/">首页</a>'), encoding='utf-8')
    summary = {'articles': len(page_rows), 'courses': len(course_groups), 'resources': len(asset_rows), 'live_verified_articles': verified_count, 'unverified_articles': len(page_rows)-verified_count, 'conversion_text_failures': sum(not p['conversion_preserves_text'] for p in page_rows), 'issue_counts': {kind: sum(i['kind'] == kind for i in issues) for kind in sorted({i['kind'] for i in issues})}, 'repositories': metadata, 'complete_source_equivalence': False}
    page_rows.sort(key=lambda row:row['source_path'])
    jsonl(manifests / 'pages.jsonl', page_rows)
    jsonl(manifests / 'resources.jsonl', asset_rows.values())
    jsonl(manifests / 'issues.jsonl', issues)
    write_json(reports / 'summary.json', summary)
    write_json(reports / 'build-progress.json', {'completed':len(page_rows),'total':len(page_keys),'resources':len(asset_rows),'running':False})
    with (reports / '章节校验.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['源站路径', 'HTML路径', '采用来源', '源站HTTP状态', '仓库正文与源站一致', '转换保持正文一致'])
        for p in page_rows:
            writer.writerow([p['source_path'],p['target'],p['selected_source'],p['source_http_status'],p['archive_matches_live_text'],p['conversion_preserves_text']])
    for reader in readers.values():
        reader.close()
    build_home(project)
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--only',action='append',help='仅修复指定源站文章路径，要求存在上次完整构建报告')
    run(parser.parse_args())
