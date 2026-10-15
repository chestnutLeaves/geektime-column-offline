# 开发与维护

## 维护入口

本项目是根目录直接提供 HTML 的静态站。页面不在浏览器里读取作者 JSON，也不在线查询课程资料；`scripts/build_home.py` 读取 JSON、文章和资源清单，生成首页、各类目录与资料来源页。

| 入口 | 作用 |
| --- | --- |
| `scripts/dev_server.py` | 本地预览，默认 18890，只开放网站白名单 |
| `scripts/build_home.py` | 生成首页、专栏目录、技术文章目录、生活文章目录、PDF 目录和资料来源页 |
| `scripts/refresh_layout.py` | 更新阅读页外壳，保护正文并更新页面清单哈希 |
| `scripts/verify_site.py` | 检查所有公开网页的内部链接，可加 `--url` 检查 HTTP |
| `scripts/verify_integrity.py` | 检查 6,300 篇文章和资源字节是否匹配清单 |
| `scripts/resources.py` | 图片/PDF 完整性检查，以及可选离线资源包导入、导出 |
| `scripts/public_paths.py` | 预览、校验工具使用的网站白名单 |

`scripts/common.py`、`ui_common.py` 和 `course_metadata.py` 是这些入口共用的模块，不需要逐个执行。

## 样式与交互

首页 `/` 展示最近阅读和四类内容概览，技术专栏独立位于 `/courses/index.html`。首页、技术专栏、技术文章、生活文章和 PDF 使用同一套五项导航；切换分类时，页头、侧栏宽度和内容起点保持一致。专栏阅读时由章节目录独占侧栏，全站入口放在页头“书库导航”。

全站外框最大 1920px，桌面侧栏宽 256px，较窄窗口缩为 220px；阅读正文保留 1048px 上限，以控制每行长度。专栏卡片标题 21px、资料文字 17px、正文 18px。技术方向为右上角 12px 标签。卡片根据窗口在 1–4 列间切换，手机端导航改为顶部排列。

技术专栏页可组合筛选技术方向、名称、作者和年份，默认按已确认时间从新到旧排序。只知道月份的记录放在该月有具体日期的记录之后；只知道年份的记录放在该年最后。估算时间不参与已确认日期排序。技术文章、生活文章和 PDF 目录各自支持标题搜索，PDF 显示文件大小并在新标签页打开。

`ui/home.html`、`ui/courses.html`、`ui/recent-reading.html` 分别保存首页概览、专栏列表和最近阅读片段，公共外壳由 `scripts/ui_common.py` 生成。`static/browse.js` 处理目录搜索、阅读来源记录和旧首页筛选链接兼容；`static/home.js` 处理专栏筛选与排序。原有文章 URL 和阅读存储键不变。阅读页返回按钮会回到进入文章前的目录及筛选状态。

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

## 阅读点评

两份公开静态 JSON 独立维护，不写入文章正文或作者资料：

- `static/reviews/courses.json`：技术专栏点评，按专栏入口路径关联。
- `static/reviews/articles.json`：技术文章点评，包含单篇文章和长页面合集；旧 `geektime/index.html` 入口共用它。

目录页通过 `static/reviews.js` 加载对应 JSON；悬停卡片或条目、键盘聚焦、点击“阅读点评”均可查看自定义浮层。手机点击按钮查看，标题链接仍直接进入阅读。Escape、关闭按钮、点击外部或页面滚动可关闭。加载失败时可重试，不阻断阅读。

| 字段 | 维护规则 |
| --- | --- |
| `schema_version`、`kind` | 当前为 `1`；分类为 `courses` 或 `articles` |
| `reviewed_at`、`reviewer`、`methodology` | 点评日期、署名及实际审阅范围；不能把摘样写成全文审计 |
| `entries[].path`、`title` | 使用以 `/` 开头、未百分号编码的实际 HTML 路径及原目录标题；路径是关联键 |
| `recommendation` | `recommended` 值得阅读、`selective` 按需阅读、`reference` 历史参考、`uncertain` 待核验 |
| `currency` | `stable` 原理为主、`mixed` 部分需更新、`dated` 实操偏旧、`contextual` 时代背景、`unknown` 待核验 |
| `summary`、`currency_note`、`reading_advice` | 阅读价值、时效判断、阅读建议，均为纯文本 |
| `evidence` | 实际参考的站内正文路径、标题与正文区域 SHA-256；不包含导航和页脚 |
| `reference_ids`、`references` | 条目引用的官方资料及核对日期；只支持 HTTPS 外部链接 |

初版为 AI 辅助编辑判断，结合目录和正文摘样，部分版本敏感主题对照官方资料。没有逐章精读、逐图核验或逐段运行代码；《MySQL 故障诊断：如何在日志中轻松定位大事务》和《大数据算法——布隆过滤器》的本地页面仅有标题、正文为空，保留待核验状态。评级不是原作者观点，也不只按出版年份判定过时。

**仅修改点评文案时不需要 Python，也不需要重新生成 HTML**，直接更新并部署 JSON 即可。浏览器使用 `cache: no-cache` 进行缓存再验证；若使用 CDN，发布后还需按自己的缓存策略刷新。已有页面保留本次载入数据，刷新页面后读取修改。Docker 将文件打入镜像，因此采用镜像部署时才需重新构建镜像。

增删内容后同步补齐点评；修改正文后需重新审阅相关点评，再更新正文证据哈希。不要为了消除校验错误而直接批量改哈希。维护后可运行：

```powershell
python scripts/build_home.py
python scripts/verify_reviews.py --project .
```

校验会检查完整覆盖、路径和标题匹配、证据归属、正文哈希、引用完整性及目录页关联。它不会代替人工判断点评是否正确，也不会在线重新核查资料。

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

## 图片和 PDF 版本管理

`assets/**` 和 `downloads/*.pdf` 随项目提交，使用 Git LFS 保存原始文件。首次获取项目需准备 Git LFS，并完成 `git lfs pull`；正常克隆后的资源无需另找下载地址。修改这些文件后，正常提交推送即可，LFS 会一并上传对应对象。生成镜像和重复导出包仍不提交。

## 检查与报告

页面、资源及问题清单位于 `data/manifests/`，属于构建输入，不可当作日志删除。`reports/` 保存新的检查输出；`reports/archive/2026-10-14/` 保留原整理过程的证据，不代表当前版本每项检查都重新执行过。

修改公开目录范围时，同步维护 `scripts/public_paths.py`、`docker/nginx.conf`、`Dockerfile` 和 `.dockerignore`。本地服务与 Docker 只开放网站文件，资料与工具目录不应作为公开资源。
