"""全量检查生成站点的本地链接，可选对运行容器逐文件执行 HTTP HEAD 检查。"""
import argparse
import concurrent.futures
import json
import http.client
import os
import posixpath
import threading
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, quote
from common import write_json, jsonl
from public_paths import iter_public_files

class References(HTMLParser):
    """收集浏览器实际加载的资源及导航，不把代码示例当成标签。"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.external_scripts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attr in ('href', 'src', 'poster'):
            if attrs.get(attr):
                self.references.append((tag, attrs[attr]))
        if tag == 'script' and attrs.get('src', '').startswith(('http:', 'https:', '//')):
            self.external_scripts.append(attrs['src'])

def run(args):
    project = Path(args.project).resolve()
    site = project
    problems = []
    external_resources = set()
    paths = [path.relative_to(site).as_posix() for path in iter_public_files(site)]
    file_set = set(paths)
    pages = [site/p for p in paths if p.endswith('.html')]
    for page in ([] if args.http_only else pages):
        parser = References()
        parser.feed(page.read_text(encoding='utf-8'))
        relative = page.relative_to(site).as_posix()
        for tag, value in parser.references:
            if value.startswith(('#','mailto:','tel:','data:','javascript:')):
                continue
            u = urlsplit(urljoin('http://offline.local/' + quote(relative,safe='/'), value))
            if u.netloc != 'offline.local':
                if tag not in ('a',):
                    external_resources.add(value)
                continue
            target = posixpath.normpath(unquote(u.path).lstrip('/'))
            directory_index = 'index.html' if target == '.' else target.rstrip('/')+'/index.html'
            if target not in file_set and directory_index not in file_set:
                problems.append({'page': relative, 'reference': value, 'tag': tag})
        for value in parser.external_scripts:
            problems.append({'page': relative, 'external_script': value})
    summary = {'html_pages':len(pages),'markdown_files_in_site':sum(p.endswith('.md') for p in paths),'broken_local_references':len(problems),'external_resource_urls':len(external_resources),'http_checked':0,'http_failures':0}
    if args.http_only:
        previous = json.loads((project/'reports/local-validation.json').read_text(encoding='utf-8'))
        if not args.url or previous['broken_local_references'] or previous['html_pages'] != len(pages):
            raise ValueError('仅 HTTP 检查要求此前本地检查通过，且明确提供服务器 URL')
        summary.update(broken_local_references=previous['broken_local_references'],external_resource_urls=previous['external_resource_urls'])
    else:
        jsonl(project / 'reports/local-link-errors.jsonl', problems)
        write_json(project / 'reports/external-resources.json', sorted(external_resources))
    if args.url:
        origin = urlsplit(args.url)
        connections = []
        state = threading.local()
        def check(path):
            try:
                # 每个线程复用连接，避免大量短连接耗尽 Windows 临时端口。
                if not hasattr(state,'connection'):
                    cls = http.client.HTTPSConnection if origin.scheme == 'https' else http.client.HTTPConnection
                    state.connection = cls(origin.hostname,origin.port,timeout=10)
                    connections.append(state.connection)
                state.connection.request('HEAD',origin.path.rstrip('/')+'/'+quote(path,safe='/'))
                response = state.connection.getresponse()
                mime = response.getheader('Content-Type','')
                response.read()
                if response.status != 200 or (path.endswith('.html') and not mime.startswith('text/html')):
                    return {'path':path,'status':response.status,'content_type':mime}
            except Exception as e:
                if hasattr(state,'connection'):
                    state.connection.close()
                return {'path':path,'error':str(e)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            failures = [r for r in pool.map(check,paths) if r]
        for connection in connections:
            connection.close()
        summary.update(http_checked=len(paths),http_failures=len(failures),http_url=args.url)
        jsonl(project / 'reports/http-errors.jsonl',failures)
    write_json(project / 'reports/local-validation.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if problems or summary['markdown_files_in_site'] or summary['http_failures']:
        raise SystemExit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--url')
    parser.add_argument('--http-only',action='store_true',help='文件未改变且本地检查已通过时，仅重跑容器 HTTP 检查')
    run(parser.parse_args())
