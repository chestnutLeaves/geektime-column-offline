"""根据现有清单生成首页和各类内容目录，不重新转换文章或复制资源。"""
import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote
from ui_common import render_browse_page
from course_metadata import load_metadata, course_card, build_sources, publication_sort_key


# 分类用于技术专栏目录，不改变归档路径和正文内容。
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
    """首页与四类目录采用同一外壳，专栏筛选只属于专栏目录。"""
    project = Path(project)
    rows = [json.loads(line) for line in (project / 'data/manifests/pages.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    resources = [json.loads(line) for line in (project / 'data/manifests/resources.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    pdfs = [row for row in resources if row['target'].startswith('downloads/') and row['target'].endswith('.pdf')]
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
    recent = (project / 'ui/recent-reading.html').read_text(encoding='utf-8')
    replacements = {'RECENT': recent, 'COURSE_COUNT': str(len(courses)), 'ARTICLE_COUNT': f'{len(rows):,}', 'PDF_COUNT': str(len(pdfs)), 'CARDS': '\n'.join(cards), 'OVERVIEW': overview_content(courses, metadata, rows, pdfs)}
    home = fill_template(project / 'ui/home.html', replacements)
    catalog = fill_template(project / 'ui/courses.html', replacements)
    categories = '<div class="category-section" hidden><p class="nav-label">按技术方向探索</p><div class="category-list" role="group" aria-label="专栏技术方向">' + '\n'.join(buttons) + '</div></div>'
    write_page(project, 'index.html', render_browse_page('首页', home, 'home', page_class='home-page'))
    write_page(project, 'courses/index.html', render_browse_page('技术专栏', catalog, 'courses', categories, scripts=('home.js',), page_class='catalog-page'))
    build_collections(project, rows, pdfs)
    print(f'Browse pages refreshed: home, {len(courses)} columns, articles, life and {len(pdfs)} PDFs.', flush=True)


def fill_template(path, replacements):
    """浏览内容片段保存在 ui，公共导航由单一外壳输出。"""
    template = path.read_text(encoding='utf-8')
    for key, value in replacements.items():
        template = template.replace('@@' + key + '@@', value)
    if re.search(r'@@[A-Z_]+@@', template):
        raise ValueError(f'存在未替换的模板字段：{path.name}')
    return template


def write_page(project, target, document):
    """只写生成的入口页，文章及资源路径始终保持原有位置。"""
    (project / target).write_text(document, encoding='utf-8', newline='\n')


def overview_content(courses, metadata, rows, pdfs):
    """首页平等展示四种内容，每类用少量真实条目帮助读者选择。"""
    technical = [row for row in rows if row['source_path'].startswith(('文章/', '极客时间/'))]
    life = [row for row in rows if row['source_path'].startswith('恋爱必修课/')]
    course_links = []
    for course in courses[:3]:
        detail = metadata[course['title']]
        authors = '、'.join(detail['authors']) or '作者待核实'
        published = str(detail['published_year']) + ' 年' if detail.get('published_year') else '年份待核实'
        course_links.append((course['target'], course['title'], authors + ' · ' + published))
    def article_links(items):
        return [(row['target'], PurePosixPath(row['source_path']).name.removesuffix('.md'), '') for row in items[:3]]
    sections = [
        ('技术专栏', '/courses/index.html', f'{len(courses)} 个专栏', '按技术方向系统阅读，查看作者与发布时间。', course_links),
        ('技术文章', '/articles/index.html', f'{len(technical)} 篇内容', '独立技术文章与专栏合集，按需查阅。', article_links(technical)),
        ('生活文章', '/relationships/index.html', f'{len(life)} 篇文章', '关于亲密关系与日常相处的阅读内容。', article_links(life)),
        ('PDF 书籍', '/downloads/index.html', f'{len(pdfs)} 份 PDF', '查看书籍文件及大小，在新标签页打开或保存。', [(row['target'], PurePosixPath(row['key']).name.removesuffix('.pdf'), f'PDF · {row["size"] / 1024 / 1024:.1f} MB') for row in pdfs[:3]]),
    ]
    cards = []
    for title, url, count, description, links in sections:
        items = []
        for target, label, detail in links:
            extra = ' target="_blank" rel="noopener" title="在新标签页打开 PDF"' if target.endswith('.pdf') else ''
            meta = '<small class="overview-link-meta">' + html.escape(detail) + '</small>' if detail else ''
            items.append('<li><a href="/' + quote(target, safe='/') + '"' + extra + '><span class="overview-link-title">' + html.escape(label) + '</span>' + meta + '</a></li>')
        cards.append('<article class="overview-card"><header class="overview-heading"><h3><a href="' + url + '">' + title + '</a></h3><span class="overview-count">' + count + '</span></header><p class="overview-description">' + description + '</p><ul class="overview-links">' + ''.join(items) + '</ul><a class="overview-more" href="' + url + '">查看全部' + title + ' <span aria-hidden="true">→</span></a></article>')
    return '<section class="overview-section" aria-labelledby="overview-title"><div class="section-heading"><h2 id="overview-title">浏览书库</h2><p>选择一类内容，开始今天的阅读。</p></div><div class="overview-grid">' + ''.join(cards) + '</div></section>'


def article_list(rows):
    """输出直接指向既有文章的列表，原文路径保持不变。"""
    items = []
    for number, row in enumerate(rows, 1):
        title = html.escape(PurePosixPath(row['source_path']).name.removesuffix('.md'))
        url = '/' + quote(row['target'], safe='/')
        items.append(f'<li data-browse-item><a href="{url}"><span class="article-index">{number:02d}</span><span class="article-title">{title}</span><span class="article-arrow" aria-hidden="true">→</span></a></li>')
    return '<ul class="article-list">' + ''.join(items) + '</ul>'


def collection_content(title, count, description, content, unit='篇内容'):
    """各类列表使用相同标题、搜索和空状态，JavaScript 不可用时保留完整目录。"""
    return (f'<header class="collection-header"><h1>{title}<span class="collection-count">{count} {unit}</span></h1><p class="collection-description">{description}</p></header>'
            f'<div class="collection-tools" hidden><div class="search-field"><label class="sr-only" for="collection-search">搜索{title}</label><input id="collection-search" type="search" placeholder="搜索{title}…" autocomplete="off"></div><p class="collection-result" id="collection-result-count" role="status">共 {count} 项</p></div>'
            '<div class="collection-panel">' + content + '<p class="collection-empty" id="collection-empty" hidden>没有找到匹配的内容，试试其他关键词。</p></div>')


def build_collections(project, rows, pdfs):
    """文章、生活及 PDF 目录全部走浏览外壳，完整重建与日常刷新保持一致。"""
    technical = [row for row in rows if row['source_path'].startswith('文章/')]
    collections = [row for row in rows if row['source_path'].startswith('极客时间/')]
    life = [row for row in rows if row['source_path'].startswith('恋爱必修课/')]
    groups = '<section data-browse-group><h2>单篇文章</h2>' + article_list(technical) + '</section>'
    groups += '<section data-browse-group id="collections"><h2>专栏合集</h2><p class="collection-description">以下内容以一个长页面收录，可连续阅读。</p>' + article_list(collections) + '</section>'
    body = collection_content('技术文章', len(technical) + len(collections), f'{len(technical)} 篇独立文章，另收录 {len(collections)} 份专栏合集。', groups)
    technical_page = render_browse_page('技术文章', body, 'articles')
    for target in ['articles/index.html', 'geektime/index.html']:
        (project / target).write_text(technical_page, encoding='utf-8', newline='\n')
    body = collection_content('生活文章', len(life), '关于亲密关系的阅读内容，来自「恋爱必修课」。', '<section data-browse-group>' + article_list(life) + '</section>')
    write_page(project, 'relationships/index.html', render_browse_page('生活文章', body, 'life'))
    pdf_items = []
    for number, row in enumerate(pdfs, 1):
        title = html.escape(PurePosixPath(row['key']).name.removesuffix('.pdf'))
        url = '/' + quote(row['target'], safe='/')
        size = f'{row["size"] / 1024 / 1024:.1f} MB'
        pdf_items.append(f'<li data-browse-item><a href="{url}" target="_blank" rel="noopener" title="在新标签页打开 PDF"><span class="article-index">{number:02d}</span><span class="article-title">{title}<small class="file-meta">PDF · {size}</small></span><span class="article-arrow" aria-hidden="true">↗</span></a></li>')
    body = collection_content('PDF 书籍', len(pdfs), '点击书籍在新标签页打开 PDF，也可使用浏览器保存到本地。', '<section data-browse-group><ul class="article-list">' + ''.join(pdf_items) + '</ul></section>', '份 PDF')
    write_page(project, 'downloads/index.html', render_browse_page('PDF 书籍', body, 'pdf'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    build_home(parser.parse_args().project)
