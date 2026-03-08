> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

配置层 - Pydantic 配置模型和加载器。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `schema.py` | 核心 | Pydantic 配置模型定义 (AgentConfig, GatewayConfig, ProviderSettings, ToolsConfig, LogConfig, SecurityConfig, KnowledgeConfig, MindClawConfig) |
| `loader.py` | 核心 | JSON 配置文件加载 + 环境变量解析 |
