> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

配置层 - Pydantic 配置模型和加载器。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `schema.py` | 核心 | Pydantic 配置模型定义 (AgentConfig 含 max_concurrent_tasks/cron_enabled, ChannelConfig, GatewayConfig, ProviderSettings, ToolsConfig 含 api_call_auth_profiles/api_call_url_allowlist/twitter_cli_path, AuthProfileConfig, LogConfig, SecurityConfig, KnowledgeConfig + ObsidianConfig/NotionConfig/WebArchiveConfig/VectorDbConfig, SkillsConfig, MindClawConfig) |
| `loader.py` | 核心 | JSON 配置文件加载 + 环境变量解析 |
