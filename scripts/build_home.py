"""根据已有文章清单生成首页；不重新转换文章，不复制图片或打包镜像。"""
import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote
from ui_common import header_html, library_nav, render_page
from course_metadata import load_metadata, course_card, build_sources, publication_sort_key


# 分类仅用于首页导航，不改变源站目录和任何正文内容。
CATEGORIES = {
    'backend': '后端与语言',
    'architecture': '架构与分布式',
    'data': '数据库与中间件',
    'frontend': '前端与移动端',
    'foundation': '计算机基础',
    'cloud': '云原生与运维',
    'ai': 'AI 与大数据',
    'growth': '工程与个人成长',
}


def categorize(title):
    """按课程名称匹配阅读方向；具体技术优先于宽泛的工程主题。"""
    lower = title.lower()
    rules = [
        ('cloud', r'docker|kubernetes|cncf|serverless|devops|jenkins|linux|运维|容器|云计算|可观测|容量保障'),
        ('ai', r'^ai|成为ai|人工智能|机器学习|pytorch|大数据|大规模数据|spark|推荐系统|ab 测试'),
        ('data', r'mysql|redis|kafka|rocketmq|shardingsphere|elasticsearch|zookeeper|etcd|数据库|缓存|中间件|消息队列'),
        ('frontend', r'前端|javascript|android|ios|flutter|webassembly|低代码|游戏开发'),
        ('foundation', r'计算机|编译|操作系统|数据结构|算法|动态规划|数学|网络协议|http协议|正则表达式'),
        ('architecture', r'架构|分布式|微服务|高并发|领域驱动|ddd|秒杀|即时消息'),
        ('growth', r'面试|管理|领导|工作法|进阶攻略|精进|代码之丑|设计模式|测试|质量|性能工程|软件工程|持续交付|法律|财富|增长|产品|短视频|广告|设计进阶|复盘|商业|访谈|okr|市场|左耳听风|区块链|web 3|vim'),
    ]
    return next((key for key, pattern in rules if re.search(pattern, lower)), 'backend')


def build_home(project):
    """从已生成文章清单汇总所有专栏，保留原有课程入口。"""
    project = Path(project)
    rows = [json.loads(line) for line in (project / 'data/manifests/pages.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    grouped = defaultdict(list)
    for row in rows:
        if row['source_path'].startswith('专栏/'):
            grouped[row['source_path'].rsplit('/', 1)[0]].append(row)
    metadata = load_metadata(project)
    # 月份已知的条目放在对应月的日级日期之后；只有年份的条目放在该年末尾。
    ordered = sorted(grouped, key=lambda key: (
        -publication_sort_key(metadata[key.split('/')[-1]]),
        key,
    ))
    courses = []
    for group in ordered:
        title = group.split('/')[-1]
        target = str(PurePosixPath(grouped[group][0]['target']).parent / 'index.html')
        if not (project / target).is_file():
            raise ValueError(f'课程入口不存在：{target}')
        courses.append({'title': title, 'target': target, 'category': categorize(title), 'count': len(grouped[group])})
    counts = Counter(course['category'] for course in courses)
    buttons = []
    for key, label, amount in [('all', '全部方向', len(courses))] + [(key, label, counts[key]) for key, label in CATEGORIES.items()]:
        buttons.append(f'<button class="category-button" type="button" data-category="{key}" data-label="{label}" aria-pressed="{str(key == "all").lower()}"><span class="category-dot" aria-hidden="true"></span>{label}<span class="nav-count">{amount}</span></button>')
    if set(metadata) != {course['title'] for course in courses}:
        raise ValueError('专栏资料与本地目录不一致，请核对 data/course-metadata.json')
    cards = [course_card(course, metadata, CATEGORIES[course['category']]) for course in courses]
    build_sources(project, metadata)
    template = (project / 'ui/home.html').read_text(encoding='utf-8')
    replacements = {'HEADER': header_html(), 'NAVIGATION': library_nav('courses'), 'COURSE_COUNT': str(len(courses)), 'ARTICLE_COUNT': f'{len(rows):,}', 'PDF_COUNT': str(sum(1 for line in (project / 'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines() if json.loads(line)['target'].startswith('downloads/') and json.loads(line)['target'].endswith('.pdf'))), 'CATEGORY_BUTTONS': '\n'.join(buttons), 'CARDS': '\n'.join(cards)}
    for key, value in replacements.items():
        template = template.replace('@@' + key + '@@', value)
    if re.search(r'@@[A-Z_]+@@', template):
        raise ValueError('首页存在未替换的模板字段')
    (project / 'index.html').write_text(template, encoding='utf-8', newline='\n')
    (project / 'courses/index.html').write_text(template, encoding='utf-8', newline='\n')
    build_collections(project, rows)
    print(f'Homepage: {len(courses)} columns. Article directories refreshed; article bodies unchanged.', flush=True)


def article_list(rows):
    """输出直接指向既有文章的列表，原文路径保持不变。"""
    items = []
    for number, row in enumerate(rows, 1):
        title = html.escape(PurePosixPath(row['source_path']).name.removesuffix('.md'))
        url = '/' + quote(row['target'], safe='/')
        items.append(f'<li><a href="{url}"><span class="article-index">{number:02d}</span><span class="article-title">{title}</span><span class="article-arrow" aria-hidden="true">↗</span></a></li>')
    return '<ul class="article-list">' + ''.join(items) + '</ul>'


def build_collections(project, rows):
    """将独立技术文章和单文件专栏合集集中展示，生活文章单独保留。"""
    technical = [row for row in rows if row['source_path'].startswith('文章/')]
    collections = [row for row in rows if row['source_path'].startswith('极客时间/')]
    life = [row for row in rows if row['source_path'].startswith('恋爱必修课/')]
    body = f'<h1>技术文章 <span class="collection-count">{len(technical) + len(collections)} 篇内容</span></h1><p class="collection-description">{len(technical)} 篇独立文章，另收录 {len(collections)} 份可连续阅读的专栏合集。</p>'
    body += '<h2>单篇文章</h2>' + article_list(technical)
    body += '<h2 id="collections">专栏合集</h2><p class="collection-description">以下内容以一个长页面收录，可直接打开阅读。</p>' + article_list(collections)
    technical_page = render_page('技术文章', body, active='articles')
    for target in ['articles/index.html', 'geektime/index.html']:
        (project / target).write_text(technical_page, encoding='utf-8', newline='\n')
    body = f'<h1>生活文章 <span class="collection-count">{len(life)} 篇内容</span></h1><p class="collection-description">关于亲密关系的阅读内容，来自「恋爱必修课」。</p>' + article_list(life)
    (project / 'relationships/index.html').write_text(render_page('生活文章', body, active='life'), encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    build_home(parser.parse_args().project)
