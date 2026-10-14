"""低频、可续跑的源站校验；403 不绕过，429 按响应要求退避。"""

# 允许从任意工作目录运行维护工具，同时复用上一级公共模块。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import concurrent.futures
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from bs4 import BeautifulSoup
from common import ORIGIN, HOSTS, CATEGORIES, canonical, source_url, digest, write_json, jsonl

class Fetcher:
    """所有线程共享访问间隔与限流冷却时间。"""
    def __init__(self, interval):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_time = 0
        self.blocked = set()

    def fetch(self, url):
        for attempt in range(2):
            with self.lock:
                when = max(time.monotonic(), self.next_time)
                self.next_time = when + self.interval
            time.sleep(max(0, when - time.monotonic()))
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; personal-offline-verification/1.0)', 'Accept-Encoding': 'identity'})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read(), {'status': r.status, 'content_type': r.headers.get('Content-Type', ''), 'final_url': r.url}
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    delay = max(60, int(e.headers.get('Retry-After', '60')) if e.headers.get('Retry-After', '60').isdigit() else 60)
                    with self.lock:
                        self.interval = min(3, self.interval * 2)
                        self.next_time = max(self.next_time, time.monotonic() + delay)
                    if attempt == 0:
                        continue
                return None, {'status': e.code, 'error': str(e)}
            except Exception as e:
                if attempt == 0:
                    time.sleep(3)
                    continue
                return None, {'status': 'error', 'error': str(e)}

def run(args):
    root = Path(args.project).resolve()
    audit = root / 'data/provenance'
    cache = root / 'data/provenance/snapshots'
    cache.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(args.interval)
    report_file = audit / ('source-' + args.phase + '.jsonl')
    results = {}
    if report_file.exists():
        for line in report_file.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            results[row['key']] = row
    if args.phase == 'pages':
        manifest = json.loads(Path(args.seed).read_text(encoding='utf-8-sig'))
        paths = set()
        for item in manifest:
            p = item['path']
            if p.startswith('book/'):
                p = p[5:]
            else:
                continue
            if p.endswith('.md') or p.endswith('/index.html') or p == 'index.html':
                paths.add(p)
        # 先读取导航页，发现原仓库中没有的新章节。
        catalogs = sorted(p for p in paths if p.endswith('index.html'))
        for catalog_number, p in enumerate(catalogs, 1):
            if p in results and results[p].get('status') == 200:
                saved = root / results[p].get('cache', '')
                data = saved.read_bytes() if saved.is_file() else None
            else:
                url = source_url(p[:-10] if p.endswith('index.html') else p)
                data, result = fetcher.fetch(url)
                row = {'key': p, 'url': url, **result, 'checked_at': datetime.now(timezone.utc).isoformat()}
                if data is not None:
                    file = cache / (digest(url.encode()) + '.html')
                    file.write_bytes(data)
                    row.update(cache=str(file.relative_to(root)).replace('\\', '/'), sha256=digest(data))
                results[p] = row
                with report_file.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
            if data:
                soup = BeautifulSoup(data, 'html.parser')
                for a in soup.find_all('a', href=True):
                    u = urlsplit(urljoin(ORIGIN + '/', a['href']))
                    candidate = unquote(u.path).lstrip('/')
                    if u.netloc in HOSTS and candidate.endswith('.md') and candidate.split('/')[0] in CATEGORIES:
                        paths.add(candidate)
            write_json(audit / 'progress-pages.json', {'phase': 'catalogs', 'completed': catalog_number, 'total': len(catalogs), 'running': True})
            if catalog_number % 10 == 0:
                print(json.dumps({'catalogs': catalog_number, 'total': len(catalogs)}, ensure_ascii=False), flush=True)
        tasks = [{'key': p, 'url': source_url(p)} for p in sorted(paths) if p.endswith('.md') and p.split('/')[0] in CATEGORIES]
        write_json(audit / 'source-catalog.json', {'paths': sorted(paths), 'count': len(paths)})
    else:
        tasks = [json.loads(line) for line in (root / 'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines()]
        tasks = [{'key': r['source_url'], 'url': r['source_url'], 'target': r['target'], 'local_sha256': r['sha256']} for r in tasks]
        # 一张资源被多个页面引用时仅请求一次。
        tasks = list({t['key']: t for t in tasks}.values())
    pending = [t for t in tasks if results.get(t['key'], {}).get('status') != 200]
    total = len(tasks)
    done = total - len(pending)
    summary = {'phase': args.phase, 'completed': done, 'total': total, 'running': True}

    def job(task):
        data, result = fetcher.fetch(task['url'])
        row = {**task, **result, 'checked_at': datetime.now(timezone.utc).isoformat()}
        if data is not None:
            row['sha256'] = digest(data)
            if args.phase == 'pages':
                soup = BeautifulSoup(data, 'html.parser')
                if not soup.select_one('.book-post'):
                    row.update(status='invalid_html', error='未找到文章正文，不能视为成功')
                else:
                    file = cache / (digest(task['url'].encode()) + '.html')
                    file.write_bytes(data)
                    row['cache'] = str(file.relative_to(root)).replace('\\', '/')
            else:
                row['matches_local_bytes'] = row['sha256'] == task['local_sha256']
                if not row['matches_local_bytes']:
                    file = cache / (digest(task['url'].encode()) + '.bin')
                    file.write_bytes(data)
                    row['cache'] = str(file.relative_to(root)).replace('\\', '/')
        return row

    # 只调度少量正在处理的请求，确保 Ctrl+C 不会继续排队执行数千次请求。
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.workers)
    queue = iter(pending)
    futures = set()
    for _ in range(args.workers):
        task = next(queue, None)
        if task is not None:
            futures.add(pool.submit(job,task))
    limits = 0
    stop_reason = None
    try:
        while futures:
            finished, futures = concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                row = future.result()
                results[row['key']] = row
                with report_file.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
                done += 1
                limits += row['status'] == 429
                if limits >= 3:
                    stop_reason = '源站持续返回 429，已停止调度新请求；请稍后低频续跑。'
                checked = [results[t['key']] for t in tasks if t['key'] in results]
                summary = {'phase': args.phase, 'completed': done, 'total': total, 'success': sum(r.get('status') == 200 for r in checked), 'failed': sum(r.get('status') != 200 for r in checked), 'interval': fetcher.interval, 'running': True}
                write_json(audit / ('progress-' + args.phase + '.json'), summary)
                if done % 50 == 0 or row['status'] != 200:
                    print(json.dumps({**summary, 'last': row['key'], 'last_status': row['status']}, ensure_ascii=False), flush=True)
                task = next(queue,None) if not stop_reason else None
                if task is not None:
                    futures.add(pool.submit(job,task))
    except KeyboardInterrupt:
        stop_reason = '用户中断；已保存完成结果，可续跑。'
    finally:
        pool.shutdown(wait=False,cancel_futures=True)
    summary['running'] = False
    summary['stop_reason'] = stop_reason
    summary['remaining'] = total - done
    write_json(audit / ('progress-' + args.phase + '.json'), summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--seed')
    parser.add_argument('--phase', choices=['pages', 'resources'], default='pages')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--interval', type=float, default=3)
    run(parser.parse_args())
