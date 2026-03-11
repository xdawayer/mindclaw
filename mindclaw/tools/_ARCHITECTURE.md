> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

工具层 - Tool 抽象基类 + 内置工具实现。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `base.py` | 核心抽象 | Tool ABC + RiskLevel 枚举，含 `max_result_chars: int | None = None` 类属性 (per-tool 截断覆盖) |
| `_ssrf.py` | 安全模块 | 共享 SSRF 防护 (is_safe_url)，供 web.py 和 api_call.py 使用 |
| `registry.py` | 核心 | ToolRegistry 注册表 |
| `file_ops.py` | 内置工具 | 文件操作工具 (ReadFile/WriteFile/EditFile/ListDir)，原子写入，路径沙箱委托 security/sandbox |
| `shell.py` | 内置工具 | Shell 执行工具 (ExecTool)，超时保护和进程组终止，命令黑名单委托 security/sandbox |
| `web.py` | 内置工具 | WebFetchTool (流式网页抓取 + SSRF 防护, max_result_chars=5000) + WebSearchTool (Tavily 搜索, max_result_chars=3000) |
| `message_user.py` | 内置工具 | MessageUserTool - 主动发消息给用户 (MODERATE)，channel/chat_id 由 AgentLoop 动态更新 |
| `spawn_task.py` | 内置工具 | SpawnTaskTool - 派发子 Agent 任务 (DANGEROUS)，通过 SubAgentManager 管理 |
| `cron.py` | 内置工具 | CronAddTool / CronListTool / CronRemoveTool / CronToggleTool / CronHistoryTool - 定时任务 CRUD + 执行历史查询 |
| `memory.py` | 内置工具 | MemorySaveTool (MODERATE) + MemorySearchTool (SAFE) — 长期记忆保存/语义+关键词搜索 |
| `skill_tools.py` | 内置工具 | LLM 技能管理工具集: skill_search(MODERATE)/skill_show(SAFE)/skill_install(DANGEROUS)/skill_remove(DANGEROUS)/skill_list(SAFE) |
| `api_call.py` | 内置工具 | ApiCallTool (DANGEROUS) — 带 URL 白名单、SSRF 防护、Auth Profile 注入的 HTTP API 调用工具 |
| `web_snapshot.py` | 内置工具 | WebSnapshotTool (MODERATE, 保存网页快照) + WebSnapshotListTool (SAFE, 列出快照) + WebSnapshotReadTool (SAFE, 读取快照) — UUID 文件名 + SSRF 防护 |
| `twitter_read.py` | 内置工具 | TwitterReadTool (MODERATE) — 通过 CLI 子进程安全读取 X/Twitter (timeline/search/user)，shell 注入防护 |
| `dashboard_export.py` | 内置工具 | DashboardExportTool (MODERATE) — 生成自包含 HTML 系统仪表盘 (cron 任务状态/执行历史/成功率) |
