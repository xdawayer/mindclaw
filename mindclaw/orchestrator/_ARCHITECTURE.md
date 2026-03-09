> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

编排层 - Agent 推理循环和子 Agent 管理。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `agent_loop.py` | 核心 | AgentLoop 主推理循环 (ReAct)，含工具调用集成、危险工具拦截、审批工作流集成、历史消息裁剪、SessionStore 持久化、ContextBuilder 动态系统提示、自动记忆整合触发和会话中毒保护 (错误时不持久化) |
| `context.py` | 核心 | ContextBuilder 动态构建系统提示，注入记忆 (MEMORY.md) 和当前日期 |
