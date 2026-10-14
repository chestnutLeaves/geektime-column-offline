"""离线站点的路径、Git 对象及正文校验工具。"""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
from bs4 import BeautifulSoup, SoupStrainer

ORIGIN = 'https://learn.lianglianglee.com'
HOSTS = {'learn.lianglianglee.com', 'lianglianglee.com'}
CATEGORIES = {'专栏': 'courses', '文章': 'articles', '极客时间': 'geektime', '恋爱必修课': 'relationships', 'PDF': 'downloads'}

def write_json(path, value):
    """原子保存报告，避免中断时留下半个 JSON。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def source_url(path):
    return ORIGIN + '/' + quote(path.lstrip('/'), safe='/')

def canonical(path):
    """统一两个备份的文章后缀，保留原始中文标题。"""
    return path[:-5] if path.endswith('.md.html') else path

def safe_name(name):
    """将 Windows 禁止的字符转换为全角字符，附带处理保留文件名。"""
    result = name.translate(str.maketrans('<>:"/\\|?*', '＜＞：＂／＼｜？＊')).rstrip('. ')
    if re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', result):
        result = '_' + result
    return result or '_'

def output_page(path):
    parts = path.split('/')
    parts[0] = CATEGORIES.get(parts[0], parts[0])
    if parts[-1].endswith('.md'):
        parts[-1] = parts[-1][:-3] + '.html'
    return '/'.join(safe_name(p) for p in parts)

def article_body(raw):
    """只提取文章区域，正文不经过 Markdown 转换。"""
    # 归档页面使用 UTF-8；禁止自动猜测编码而静默替换正文字符。
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig')
    soup = BeautifulSoup(raw, 'html.parser', parse_only=SoupStrainer(class_='book-post'))
    post = soup.select_one('.book-post')
    return soup, post

def semantic_text(post):
    """正文比较忽略排版空白和历史关站通知，不忽略其他文字。"""
    if post is None:
        return ''
    text = re.sub(r'\s+', '', post.get_text())
    return text.replace('因收到Google相关通知，网站将会择期关闭。相关通知内容', '')

def tree(repo):
    """读取 Git 文件树而不检出，兼容原仓库的非法 Windows 文件名。"""
    raw = subprocess.check_output(['git', '--git-dir', str(repo), 'ls-tree', '-rz', 'HEAD'])
    result = {}
    for item in raw.split(b'\0'):
        if not item:
            continue
        meta, name = item.split(b'\t', 1)
        mode, kind, sha = meta.split()
        if kind == b'blob':
            result[name.decode('utf-8')] = sha.decode('ascii')
    return result

class GitReader:
    """复用 cat-file 进程，顺序读取原始对象而不执行仓库代码。"""
    def __init__(self, repo):
        self.process = subprocess.Popen(['git', '--git-dir', str(repo), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, sha):
        self.process.stdin.write((sha + '\n').encode('ascii'))
        self.process.stdin.flush()
        header = self.process.stdout.readline().split()
        if len(header) != 3:
            raise RuntimeError('Git 对象不存在: ' + sha)
        size = int(header[2])
        data = self.process.stdout.read(size)
        if len(data) != size or self.process.stdout.read(1) != b'\n':
            raise RuntimeError('Git 对象读取不完整: ' + sha)
        return data

    def close(self):
        self.process.stdin.close()
        self.process.wait()
