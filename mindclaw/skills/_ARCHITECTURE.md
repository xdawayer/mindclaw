> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

技能层 - Markdown 技能文件 + SkillRegistry 多目录注册中心 + 安装系统，LLM 自主路由选择技能。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `registry.py` | 核心 | SkillRegistry 多目录扫描(builtin/project/user)，原子重载，保护名称集合 |
| `installer.py` | 核心 | 技能安装/卸载/更新，支持本地/URL/GitHub/索引四种源 |
| `index_client.py` | 核心 | 集中索引拉取、本地缓存(TTL 24h)、技能搜索 |
| `integrity.py` | 安全 | SHA256 校验、SSRF 过滤、格式验证、大小限制 |
| `summarize.md` | 内置技能 | URL/文件/YouTube 总结提取 (summarize CLI) (on_demand) |
| `translate.md` | 内置技能 | 翻译技能 (on_demand) |
| `hot-news.md` | 内置技能 | 热点新闻聚合 - 多类别搜索+摘要日报 (on_demand) |
| `competitor-monitor.md` | 内置技能 | 竞品监控 - 网页快照对比+语义差异分析 (on_demand) |
| `seo-article.md` | 内置技能 | SEO 文章生成 - 关键词研究+草稿写作 (on_demand) |
| `content-publish.md` | 内置技能 | 跨平台发布 - 通过 api_call 发布内容 (on_demand) |
| `twitter-browse.md` | 内置技能 | X/Twitter 浏览 - 时间线/搜索/用户动态摘要 (on_demand) |
| `dashboard.md` | 内置技能 | 系统仪表盘 - 生成 HTML 状态看板 (on_demand) |
| `agent-browser.md` | 内置技能 | 无头浏览器自动化 - 通过 exec + agent-browser CLI (on_demand) |
| `github-ops.md` | 内置技能 | GitHub 操作 - 通过 exec + gh CLI (on_demand) |
| `google-workspace.md` | 内置技能 | Google Workspace - 通过 exec + gog CLI (on_demand) |
| `self-improving.md` | 内置技能 | 自我改进 - 记录错误/纠正/学习 (always) |
