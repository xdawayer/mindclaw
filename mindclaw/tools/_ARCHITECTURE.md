> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

工具层 - Tool 抽象基类 + 内置工具实现。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `base.py` | 核心抽象 | Tool ABC + RiskLevel 枚举 |
| `registry.py` | 核心 | ToolRegistry 注册表 |
| `shell.py` | 内置工具 | Shell 执行工具 (ExecTool)，含命令黑名单和超时保护 |
| `web.py` | 内置工具 | WebFetchTool (网页抓取) + WebSearchTool (Brave 搜索) |
