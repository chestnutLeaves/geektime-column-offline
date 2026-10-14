# 检查报告

根层保存当前项目运行检查后生成的报告，默认不提交 Git；`archive/2026-10-14/` 是此前整理与页面开发的历史证据，保留在版本控制中。

- `repository-layout-validation.json`：本次迁移、路径、页面和工具检查汇总。
- `local-validation.json`：公开 HTML 内部链接检查，可选包含 HTTP 验证。
- `integrity.json`：文章和图片/PDF 与清单的哈希检查。
- `layout-refresh.json`：更新页面外壳时的正文保护检查。

构建必需的 `pages.jsonl`、`resources.jsonl` 和 `issues.jsonl` 已迁至 `data/manifests/`，不能把它们当日志删除。历史报告内的旧路径和容器信息只描述当时结果，不是新项目的运行配置。
