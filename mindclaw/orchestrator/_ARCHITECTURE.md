> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

编排层 - Agent 推理循环、ACP 协议、子 Agent 管理。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `agent_loop.py` | 核心 | AgentLoop 主推理循环 (ReAct)，含工具调用集成、危险工具拦截、审批工作流集成、历史消息裁剪、SessionStore 持久化、ContextBuilder 动态系统提示、自动记忆整合触发、会话中毒保护 (错误时不持久化)、cron 执行约束 (blocked_tools/max_iterations/timeout)、per-tool max_result_chars 覆盖、cron 专用系统提示; 导出 current_channel_var/current_chat_id_var (ContextVar，per-task 路由上下文，消除并发共享状态竞态) |
| `context.py` | 核心 | ContextBuilder 动态构建系统提示，注入记忆 (MEMORY.md)、当前日期、可选技能摘要 (skill_registry)、always 技能内容、向量语义搜索结果 (abuild_system_prompt)、cron 专用系统提示 (build_cron_system_prompt: 含输出语言/格式/长度约束、数据采集策略、质量标准) |
| `acp.py` | 核心 | ACP 协议 - AgentHandle 管理子 Agent 进程生命周期 (asyncio.subprocess + JSON stdin/stdout)，TaskRequest/TaskResult 数据类，AgentStatus 枚举 |
| `subagent.py` | 核心 | SubAgentManager 子 Agent 管理器 - 并发控制 (默认 max 3)、任务派发、结果汇总、超时管理 |
| `subagent_runner.py` | 辅助 | 子 Agent 子进程入口点 (python -m)，从 stdin 读 TaskRequest JSON，输出 TaskResult JSON 到 stdout |
| `cron_scheduler.py` | 核心 | CronScheduler - 后台 asyncio 任务，定期检查 cron 表达式，触发到期任务回调，支持 global_enabled_fn 全局开关 |
| `cron_store.py` | 核心 | CronTaskStore - cron 任务持久化层，asyncio.Lock + 原子写入 (.tmp + rename)，供 scheduler 和 tools 共享 |
| `cron_context.py` | 辅助 | CronExecutionConstraints - 无人值守 cron 执行约束 (max_iterations/timeout/blocked_tools)，parse 函数 |
| `cron_logger.py` | 辅助 | CronRunLogger - 追加写入 cron_runs.jsonl，log_run() 写入执行记录，recent_runs() 读取并过滤 |
