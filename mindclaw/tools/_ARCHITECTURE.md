> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

工具层 - Tool 抽象基类 + 内置工具实现。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `base.py` | 核心抽象 | Tool ABC + RiskLevel 枚举 |
| `registry.py` | 核心 | ToolRegistry 注册表 |
| `file_ops.py` | 内置工具 | 文件操作工具 (ReadFile/WriteFile/EditFile/ListDir)，原子写入，路径沙箱委托 security/sandbox |
| `shell.py` | 内置工具 | Shell 执行工具 (ExecTool)，超时保护和进程组终止，命令黑名单委托 security/sandbox |
| `web.py` | 内置工具 | WebFetchTool (流式网页抓取 + SSRF 防护) + WebSearchTool (Brave 搜索) |
| `message_user.py` | 内置工具 | MessageUserTool - 主动发消息给用户 (MODERATE)，channel/chat_id 由 AgentLoop 动态更新 |
| `spawn_task.py` | 内置工具 | SpawnTaskTool - 派发子 Agent 任务 (DANGEROUS)，通过 SubAgentManager 管理 |
| `cron.py` | 内置工具 | CronAddTool / CronListTool / CronRemoveTool - 定时任务 CRUD (MODERATE)，持久化到 cron_tasks.json |
| `memory.py` | 内置工具 | MemorySaveTool (MODERATE) + MemorySearchTool (SAFE) — 长期记忆保存/语义+关键词搜索 |
| `skill_tools.py` | 内置工具 | LLM 技能管理工具集: skill_search(MODERATE)/skill_show(SAFE)/skill_install(DANGEROUS)/skill_remove(DANGEROUS)/skill_list(SAFE) |
