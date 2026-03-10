> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

MindClaw 主包入口，包含 6 层架构的所有子模块。

| 文件/目录 | 地位 | 功能 |
|-----------|------|------|
| `__init__.py` | 包入口 | 导出 __version__ |
| `app.py` | 顶层编排器 | MindClawApp：统一管理组件生命周期和消息路由 |
| `cli/` | 用户接口层 | CLI 命令定义 (Typer) |
| `gateway/` | 网关层 | WebSocket Gateway |
| `channels/` | 渠道层 | 各平台渠道适配 |
| `bus/` | 消息总线层 | 异步消息路由 |
| `orchestrator/` | 编排层 | Agent Loop + 子 Agent |
| `llm/` | 大脑层 | LLM 路由 + 缓存 |
| `security/` | 安全层 | 认证 + 审批 + 沙箱 |
| `tools/` | 工具层 | 工具抽象 + 内置工具 |
| `plugins/` | 插件系统 | 插件加载 + Hook |
| `knowledge/` | 知识层 | 记忆 + 知识源 |
| `config/` | 配置层 | Pydantic 配置 |
| `skills/` | 技能层 | SkillRegistry + Markdown 技能文件 (YAML front-matter) |
| `health/` | 健康检查 | HealthMonitor (运行状态) + HealthCheckServer (HTTP /health /ready) |
| `templates/` | 模板 | SOUL.md / AGENTS.md |
