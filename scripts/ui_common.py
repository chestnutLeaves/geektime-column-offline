"""首页、目录页和阅读页共用的导航与页面外壳；不处理归档正文。"""
import html
import re
from urllib.parse import unquote, urlsplit

NAVIGATION = [
    ('home', '/', '首页', '⌂'),
    ('courses', '/courses/index.html', '技术专栏', '▦'),
    ('articles', '/articles/index.html', '技术文章', '≡'),
    ('life', '/relationships/index.html', '生活文章', '♡'),
    ('pdf', '/downloads/index.html', 'PDF 书籍', '▤'),
]


def header_html(reading=False, active='courses'):
    """阅读时将全站入口收进顶部菜单，让侧栏专注于当前目录。"""
    brand = '<a class="brand" href="/" aria-label="技术阅读库首页"><span class="brand-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 6c-3-2-6-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v14"/></svg></span><span>技术阅读库<small>专栏 · 文章 · 书籍</small></span></a>'
    if reading:
        links = []
        for key, url, label, icon in NAVIGATION:
            selected = ' selected' if key == active else ''
            links.append(f'<a class="switcher-link{selected}" data-section="{key}" href="{url}"><span aria-hidden="true">{icon}</span>{label}</a>')
        action = '<details class="library-switcher"><summary>书库导航<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></summary><nav class="switcher-panel" aria-label="书库导航">' + ''.join(links) + '<a class="switcher-about" href="/about.html">关于书库</a></nav></details>'
    else:
        action = '<a class="about-link" href="/about.html">关于书库 <span aria-hidden="true">↗</span></a>'
    return '<header class="topbar">' + brand + action + '</header>'


def library_nav(active='home'):
    """首页和四个内容目录共用入口顺序，以当前位置决定高亮。"""
    links = []
    for key, url, label, icon in NAVIGATION:
        selected = ' selected' if key == active else ''
        current = ' aria-current="page"' if key == active else ''
        links.append(f'<a class="shelf-link{selected}" href="{url}"{current}><span class="nav-icon" aria-hidden="true">{icon}</span>{label}</a>')
    return '<nav class="library-nav" aria-label="内容目录"><p class="nav-label">内容目录</p><div class="library-nav-links">' + ''.join(links) + '</div></nav>'


def active_section(value):
    """兼容源站路径、生成路径与页面标题，保留旧链接的导航归属。"""
    value = unquote(urlsplit(value or '').path).strip('/')
    if value in ('', 'index.html'):
        return 'home'
    if value.startswith(('articles', 'geektime', '文章', '极客时间', '技术文章')):
        return 'articles'
    if value.startswith(('relationships', '恋爱必修课', '生活文章')):
        return 'life'
    if value.startswith(('downloads', 'PDF')):
        return 'pdf'
    if value.startswith(('about', '关于')):
        return ''
    return 'courses'


def render_browse_page(title, content, active, sidebar_extra='', scripts=(), page_class=''):
    """目录页统一使用浏览外壳，避免误用窄正文容器而使侧栏跳动。"""
    extra_scripts = ''.join(f'<script src="/static/{html.escape(name, quote=True)}" defer></script>' for name in scripts)
    footer = '<footer class="home-footer"><span>技术阅读库 · 知识常读常新</span><a href="/about.html">内容来源与整理说明</a></footer>'
    return ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="description" content="技术专栏、技术文章、生活文章与 PDF 书籍，随时开始阅读。">'
            '<title>' + html.escape(title) + ' · 技术阅读库</title>'
            '<link rel="stylesheet" href="/static/home.css">'
            '<link rel="stylesheet" href="/static/reading-history.css">'
            '<script src="/static/browse.js" defer></script>'
            '<script src="/static/reading-history.js" defer></script>' + extra_scripts + '</head>'
            '<body class="browse-page ' + html.escape(page_class, quote=True) + '">'
            '<a class="skip-link" href="#main-content">跳到内容</a>' + header_html(active=active)
            + '<div class="workspace browse-layout"><aside class="sidebar home-sidebar" aria-label="浏览与筛选">'
            + library_nav(active) + sidebar_extra + '</aside><main class="browse-main" id="main-content">'
            + content + footer + '</main></div></body></html>')


def render_page(title, content, navigation='', active='courses'):
    """只包装导航及正文外壳，content 原样嵌入以保护正文和代码。"""
    navigation = navigation.replace('<p><a href="/">← 全部课程</a></p>', '')
    has_directory = '<ul>' in navigation
    if has_directory:
        directory_title = '专栏目录' if active == 'courses' else '文章目录'
        name_match = re.search(r'<strong>(.*?)</strong>', navigation, re.S)
        directory_name = name_match.group(1) if name_match else html.escape(title)
        first_link = re.search(r'href="([^"]+)"', navigation)
        overview = html.unescape(first_link.group(1)).rsplit('/', 1)[0] + '/index.html' if first_link else '/'
        chapter_count = len(re.findall(r'<li[ >]', navigation))
        entry = next((item for item in NAVIGATION if item[0] == active), NAVIGATION[0])
        heading = '<a class="library-back return-to-library" href="' + entry[1] + '">← 返回' + entry[2] + '</a><div class="chapter-heading"><span>正在阅读</span><a class="course-overview" href="' + html.escape(overview, quote=True) + '">' + directory_name + '</a></div>'
        tools = '<div class="chapter-tools" hidden><label class="sr-only" for="chapter-search">筛选章节</label><input id="chapter-search" type="search" placeholder="筛选章节…" autocomplete="off"><button id="locate-current" type="button" hidden>定位当前</button></div><p class="chapter-empty" role="status" hidden>没有匹配的章节</p>'
        # 导航原始片段保留在固定边界内，后续刷新外壳不会重复嵌套控件。
        navigation = navigation.replace('class="active"', 'class="active" aria-current="page"') if 'aria-current="page"' not in navigation else navigation
        directory = heading + '<details class="chapter-directory" open><summary>' + directory_title + f'<span class="chapter-count">{chapter_count} 篇</span><span class="chapter-toggle" aria-hidden="true">⌄</span></summary>' + tools + '<div class="chapter-links"><!-- chapter-navigation:start -->' + navigation + '<!-- chapter-navigation:end --></div></details>'
        sidebar = directory
    else:
        sidebar = library_nav(active)
    footer = '<footer class="reading-footer">内容来自 learn.lianglianglee.com 及公开备份，原作者署名与正文保留。<br><a href="/about.html">内容来源与整理说明 ↗</a></footer>'
    sidebar_class = 'sidebar reading-sidebar toc-sidebar' if has_directory else 'sidebar reading-sidebar'
    return '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + ' · 技术阅读库</title><link rel="stylesheet" href="/static/site.css"><link rel="stylesheet" href="/static/reading-history.css"><script src="/static/reader.js" defer></script><script src="/static/reading-history.js" defer></script></head><body class="reading-page"><a class="skip-link" href="#main-content">跳到正文</a>' + header_html(has_directory, active) + '<div class="workspace reading-layout"><aside class="' + sidebar_class + '">' + sidebar + '</aside><main class="reading-main" id="main-content">' + content + footer + '</main></div></body></html>'
