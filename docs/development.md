# 开发与维护

## 维护入口

本项目是根目录直接提供 HTML 的静态站。页面不在浏览器里读取作者 JSON，也不在线查询课程资料；`scripts/build_home.py` 读取 JSON 和文章清单，生成首页与资料来源页。

| 入口 | 作用 |
| --- | --- |
| `scripts/dev_server.py` | 本地预览，默认 18890，只开放网站白名单 |
| `scripts/build_home.py` | 生成首页、技术文章目录、生活文章目录、资料来源页 |
| `scripts/refresh_layout.py` | 更新阅读页外壳，保护正文并更新页面清单哈希 |
| `scripts/verify_site.py` | 检查所有公开网页的内部链接，可加 `--url` 检查 HTTP |
| `scripts/verify_integrity.py` | 检查 6,300 篇文章和资源字节是否匹配清单 |
| `scripts/resources.py` | 独立资源包检查、导入、导出 |
| `scripts/public_paths.py` | 预览、校验工具使用的网站白名单 |

`scripts/common.py`、`ui_common.py` 和 `course_metadata.py` 是这些入口共用的模块，不需要逐个执行。

## 样式与交互

首页保留技术专栏、技术文章、生活文章和 PDF 四个入口。专栏阅读时由章节目录独占侧栏，全站入口放在页头“书库导航”。

首页内容容器最大 1920px，阅读页最大 1440px；专栏卡片标题 21px、资料文字 17px、正文 18px。技术方向为右上角 12px 标签。布局根据窗口在 1–4 列间切换。

首页可组合筛选技术方向、名称、作者和年份，默认按已确认时间从新到旧排序。只知道月份的记录放在该月有具体日期的记录之后；只知道年份的记录放在该年最后。估算时间不参与已确认日期排序。

最近阅读逻辑在 `static/reading-history.js`，浏览器键为 `reading-library.history.v1`。目录页、来源页、PDF 不记录阅读位置；存储不可用时仍可正常阅读。不同访问端口属于不同存储空间。

## 元数据

`data/course-metadata.json` 按原始目录名 `title` 精确对应 159 个专栏。不要只改卡片 HTML：重新生成后会被 JSON 内容覆盖。

| 字段 | 含义 |
| --- | --- |
| `authors`、`author_role` | 作者数组；访谈可标记为嘉宾 |
| `published_date` | 已确认具体日期，格式 `YYYY-MM-DD`；未知为 `null` |
| `published_month` | 仅明确到月份时使用 `YYYY-MM`，不补造每月 1 日 |
| `published_year` | 明确年份；未知为 `null` |
| `publication_status` | 明确、估算、未知、持续文档或分篇发表；旧记录可无此字段 |
| `publication_estimate`、`publication_parts` | 独立保存估算时间或分篇时间 |
| `author_status` | 署名采用状态或冲突标记 |
| `sources`、`date_basis`、`notes` | 字段证据、时间口径及必要说明 |
| `user_review` | 人工核对原文、表格行号、处理结论及在线复核范围 |

维护后运行 `python scripts/build_home.py`。核对表原件副本保存在 `data/reviews/`，元数据与浏览器的个人阅读记录无关。

## 完整重建

仅当需要重新从原始仓库整理内容时使用以下流程。通常调整 UI、资料和阅读功能不需要执行。

```powershell
python -m pip install -r requirements.txt
python scripts/maintenance/prepare_sources.py
python scripts/maintenance/build_site.py --project .
python scripts/verify_site.py --project .
python scripts/verify_integrity.py --project .
```

准备原始仓库需要 Git 和网络。`data/upstream.json` 固定两个源仓库提交，工具只获取版本对象并保存在 `.cache/upstream/`，不检出或执行原仓库的代码。源站证据和修复快照保存在 `data/provenance/`；完整重建读取这些相对路径，不依赖旧电脑目录。

完整重建可能覆盖手工编辑的文章 HTML。文章原始正文若需要修订，应先保存明确的修改记录，不能直接把当前页面当成唯一来源。

维护工具位于 `scripts/maintenance/`，按用途分为：

- 来源：`prepare_sources.py`、`audit_source.py`、`compare_repositories.py`、`explain_differences.py`。
- 构建：`build_site.py`。
- 图片修复：`find_resource_replacements.py`、`recover_invalid_resources.py`、`fetch_supplemental_resource.py`、`repair_known_resources.py`。
- 镜像导出：`export_image.py`。

图片修复工具只在发现具体问题后使用。在线核验默认低频请求，HTTP 403、429 和失败响应不计为核验成功。历史的一次性换行修复工具及旧交付报告生成器未放入新项目，当前生成器已经固定 UTF-8 与 LF。

## 检查与报告

页面、资源及问题清单位于 `data/manifests/`，属于构建输入，不可当作日志删除。`reports/` 保存新的检查输出；`reports/archive/2026-10-14/` 保留原整理过程的证据，不代表当前版本每项检查都重新执行过。

修改公开目录范围时，同步维护 `scripts/public_paths.py`、`docker/nginx.conf`、`Dockerfile` 和 `.dockerignore`。本地服务与 Docker 只开放网站文件，资料与工具目录不应作为公开资源。
