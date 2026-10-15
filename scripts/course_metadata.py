"""读取本地专栏资料并生成卡片与查证页；浏览站点时不访问外部服务。"""
import html
import json
from pathlib import Path
from urllib.parse import quote, urlsplit
from ui_common import render_page


def load_metadata(project):
    """按原始目录名精确关联，拒绝重复条目，避免同名课程资料错配。"""
    path = Path(project) / 'data/course-metadata.json'
    rows = json.loads(path.read_text(encoding='utf-8'))['courses']
    result = {}
    for row in rows:
        if row['title'] in result:
            raise ValueError(f'重复专栏资料：{row["title"]}')
        result[row['title']] = row
    return result


def publication_sort_key(row):
    """仅用明确的时间排序；缺失月日以排序位补零，不生成或持久化虚构日期。"""
    value = row.get('published_date') or row.get('published_month') or str(row.get('published_year') or '')
    return int(value.replace('-', '').ljust(8, '0')) if value else 0


def course_card(course, metadata, category_label):
    """阅读入口与来源入口分别可聚焦，避免在整卡链接中嵌套链接。"""
    row = metadata[course['title']]
    escape = html.escape
    title = escape(course['title'], quote=True)
    authors = '、'.join(row['authors']) or '作者待核实'
    year = row.get('published_year')
    year_text = f'{year} 年' if year else ('持续更新' if row.get('publication_status') == 'not_applicable' else '年份待核实')
    author_label = row.get('author_role', '作者')
    search = escape(' '.join([course['title'], authors, str(year or '')]).lower(), quote=True)
    url = '/' + quote(course['target'], safe='/')
    published = row.get('published_date') or row.get('published_month') or ''
    year_html = f'<time datetime="{published or year}">{year_text}</time>' if year else year_text
    review_key = escape('/' + course['target'], quote=True)
    return (f'<article class="course-card" data-review-key="{review_key}" data-title="{title}" data-search="{search}" data-category="{course["category"]}" data-count="{course["count"]}" data-year="{year or 0}" data-published="{published}">'
            f'<a class="course-link" href="{url}"><span class="course-category">{category_label}</span><h2>{title}</h2>'
            f'<dl class="course-meta"><div><dt>{escape(author_label)}</dt><dd>{escape(authors)}</dd></div>'
            f'<div><dt>发布</dt><dd title="{escape(row.get("date_basis") or "尚未找到可靠的发布日期", quote=True)}">{year_html}</dd></div></dl></a>'
            f'<div class="card-bottom"><span><strong>{course["count"]}</strong> 篇文章</span>'
            f'<button class="review-trigger" type="button" hidden aria-label="阅读点评：{title}" aria-haspopup="dialog" aria-expanded="false" aria-controls="reading-review">阅读点评</button>'
            f'<a class="metadata-link" href="/course-sources.html#course-{row["id"]}" aria-label="查看{title}的资料来源">资料来源</a></div></article>')


def build_sources(project, metadata):
    """保留字段级证据及日期口径，不把转载时间、评论时间当成首发日期。"""
    escape = html.escape
    body = '<h1>专栏资料来源</h1><p>资料来自课程开篇、官方介绍、作者自述及人工核对表。时间按已确认的日、月或年保存；推广时间、推算时间和署名冲突单独说明，未确认的正式字段保留为空。每项资料的具体依据见下方。</p><p><a href="/courses/index.html">返回技术专栏</a></p>'
    authors_count = sum(bool(row['authors']) for row in metadata.values())
    year_count = sum(bool(row.get('published_year')) for row in metadata.values())
    conflict_count = sum(row.get('author_status') == 'conflict' for row in metadata.values())
    body += f'<p class="source-note">共 {len(metadata)} 个专栏，{authors_count} 项已记录作者，其中 {conflict_count} 项署名仍有争议；{year_count} 项已有明确发布年份。资料维护于项目的 data/course-metadata.json。明确字段包含采用的人工核对结果，不表示每项来源均已在本次独立在线复核。</p>'
    for row in sorted(metadata.values(), key=lambda item: item['id']):
        authors = '、'.join(row['authors']) or '待核实'
        date = row.get('published_date') or row.get('published_month') or (str(row['published_year']) + ' 年' if row.get('published_year') else '待核实')
        if row.get('publication_status') == 'not_applicable':
            date = '持续更新（无统一首发日期）'
        body += f'<section class="source-record" id="course-{row["id"]}"><h2>{escape(row["title"])}</h2><p>{escape(row.get("author_role", "作者"))}：{escape(authors)}<br>发布：{escape(date)}'
        if row.get('date_basis'):
            body += f'（{escape(row["date_basis"])}）'
        body += '</p><ul>'
        for source in row['sources']:
            url = source['url']
            if urlsplit(url).scheme not in ('http', 'https') and not url.startswith('/'):
                raise ValueError(f'来源链接格式错误：{url}')
            label = source.get('title') or '资料来源'
            body += f'<li><a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'
            if source.get('evidence'):
                body += f'<p>{escape(source["evidence"])}</p>'
            if source.get('local_url'):
                body += f'<a href="{escape(source["local_url"], quote=True)}">在本地查看原文</a>'
            body += '</li>'
        body += '</ul>'
        if row.get('notes'):
            body += f'<p class="source-note">{escape(row["notes"])}</p>'
        review = row.get('user_review')
        if review:
            submitted = review['submitted']
            # 原始核对结论始终保留，浏览者可区分已采用日期与仅供进一步查证的线索。
            body += (f'<p class="source-note">人工核对记录：{escape(review["sheet"])}第 {review["row"]} 行，'
                     f'表中时间：{escape(submitted["发布时间"])}；精度：{escape(submitted["时间精度"])}。<br>'
                     f'作者核对：{escape(submitted["登记作者核对"])}。<br>'
                     f'处理：{escape(review["date_decision"])} {escape(review["author_decision"])}<br>'
                     f'项目内原表：<code>{escape(review["source_file"])}</code></p>')
        body += '</section>'
    page = render_page('专栏资料来源', body)
    page = page.replace('</head>', '<link rel="stylesheet" href="/static/metadata.css"></head>')
    (Path(project) / 'course-sources.html').write_text(page, encoding='utf-8', newline='\n')
