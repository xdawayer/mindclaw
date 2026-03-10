> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

测试层 - pytest 测试集合。

| 文件 | 地位 | 功能 |
|------|------|------|
| `conftest.py` | 配置 | autouse fixture 隔离 data 目录，防止跨测试数据污染 |
| `__init__.py` | 包入口 | 空 |
| `test_import.py` | 冒烟测试 | 验证 mindclaw 包可导入 |
| `test_config.py` | 单元测试 | 配置系统 Schema + Loader 测试 |
| `test_llm.py` | 单元测试 | LLM 路由层 (LLMRouter + ChatResult) 测试 |
| `test_bus.py` | 单元测试 | 消息总线 (InboundMessage / OutboundMessage / MessageBus) 测试 |
| `test_agent_loop.py` | 单元测试 | 编排层 Agent Loop (AgentLoop) 测试，含 SessionStore 持久化验证和 ContextBuilder 集成验证 |
| `test_cli_channel.py` | 单元测试 | 渠道层 (BaseChannel / CLIChannel) 测试 |
| `test_tools_base.py` | 单元测试 | 工具层 (Tool ABC / RiskLevel / ToolRegistry) 测试 |
| `test_tools_shell.py` | 单元测试 | 工具层 Shell 执行 (ExecTool) 测试 |
| `test_tools_web.py` | 单元测试 | 工具层网页操作 (WebFetchTool 流式抓取 / SSRF 防护 / WebSearchTool) 测试 |
| `test_tools_file_ops.py` | 单元测试 | 工具层文件操作 (ReadFile/WriteFile/EditFile/ListDir + 路径沙箱) 测试 |
| `test_agent_loop_tools.py` | 集成测试 | 编排层 Agent Loop 工具调用集成 (ReAct 循环 + 最大迭代 + 危险工具拦截 + per-tool max_result_chars) 测试 |
| `test_security_sandbox.py` | 单元测试 | 安全层沙箱 (is_command_denied 命令黑名单 / validate_path 路径沙箱) 测试 |
| `test_security_approval.py` | 单元测试 | 安全层审批工作流 (ApprovalManager 审批/拒绝/超时/生命周期) 测试 |
| `test_message_routing.py` | 单元测试 | 消息路由测试 (审批回复路由到 ApprovalManager / 端到端审批流) |
| `test_session_store.py` | 单元测试 | SessionStore JSONL 持久化和整合指针测试 |
| `test_memory_manager.py` | 单元测试 | MemoryManager LLM 驱动记忆整合 (should_consolidate/load_memory/consolidate 流程) 测试 |
| `test_context_builder.py` | 单元测试 | ContextBuilder 动态系统提示构建 (日期注入/记忆注入/无记忆场景) 测试 |
| `test_crypto.py` | 单元测试 | SecretStore 加密存储 (初始化/读写/删除/持久化/文件权限) 测试 |
| `test_channel_manager.py` | 单元测试 | ChannelManager (注册/查找/启停生命周期/出站消息分发) 测试 |
| `test_gateway_auth.py` | 单元测试 | GatewayAuthManager (Token 验证/设备配对请求审批超时/持久化/配对回复路由) 测试 |
| `test_app.py` | 集成测试 | MindClawApp 编排器 (组件装配/工具注册/出站路由/消息路由分发) 测试 |
| `test_gateway_server.py` | 集成测试 | GatewayServer + GatewayChannel (WebSocket 认证/消息收发/ping-pong/出站推送) 测试 |
| `test_telegram_channel.py` | 单元测试 | TelegramChannel (消息接收/白名单过滤/群组过滤/发送/polling 启停) 测试 |
| `test_commands.py` | 单元测试 | CLI 命令测试 (version/secret-set/secret-list/secret-delete) |
| `test_bus_enhanced.py` | 单元测试 | 增强消息总线 (去重/限流) 测试 |
| `test_tools_spawn_task.py` | 单元测试 | SpawnTaskTool (子 Agent 创建/并发限制/结果返回) 测试 |
| `test_tools_message_user.py` | 单元测试 | MessageUserTool (出站消息发送/风险等级/上下文注入) 测试 |
| `test_orchestrator_integration.py` | 集成测试 | Orchestrator 编排层集成测试 |
| `test_acp.py` | 单元测试 | ACP 协议 (Agent 进程通信) 测试 |
| `test_subagent.py` | 单元测试 | SubAgent 管理器测试 |
| `test_plugins_hooks.py` | 单元测试 | 插件 Hook 管理器测试 |
| `test_plugin_integration.py` | 集成测试 | 插件系统集成测试 |
| `test_plugins_manifest.py` | 单元测试 | 插件清单解析测试 |
| `test_plugins_loader.py` | 单元测试 | 插件加载器测试 |
| `test_slack_channel.py` | 单元测试 | Slack 渠道 (Socket Mode 消息收发) 测试 |
| `test_discord_channel.py` | 单元测试 | Discord 渠道 (Bot gateway 消息收发) 测试 |
| `test_feishu_channel.py` | 单元测试 | 飞书渠道 (lark-oapi WebSocket) 测试 |
| `test_knowledge_text_utils.py` | 单元测试 | 共享文本工具 (html_to_text / extract_snippet) 测试 |
| `test_knowledge_obsidian.py` | 单元测试 | ObsidianKnowledge (读写/搜索/列出/标签含YAML list/链接/路径安全) 测试 |
| `test_knowledge_notion.py` | 单元测试 | NotionKnowledge (读/创建含page parent/更新/搜索/列数据库/ID验证/Block→Markdown含to_do/API key warning) 测试 |
| `test_knowledge_web_archive.py` | 单元测试 | WebArchive (保存/去重/搜索/列出/max_pages/URL验证/frontmatter防注入) 测试 |
| `test_cron_store.py` | 单元测试 | CronTaskStore CRUD、原子写入、并发安全、add_if_name_unique 测试 |
| `test_cron_scheduler.py` | 单元测试 | CronScheduler (到期判定/触发回调/disabled跳过/并发安全) 测试 |
| `test_tools_cron.py` | 单元测试 | Cron 工具 (add/list/remove/toggle/重名拒绝/notify字段/风险等级) 测试 |
| `test_cron_context.py` | 单元测试 | CronExecutionConstraints 解析、默认值、工具阻止逻辑测试 |
| `test_cron_concurrency.py` | 单元测试 | 消息路由并发控制 (bounded semaphore/信号量释放/active_tasks 清理) 测试 |
| `test_cron_agent_integration.py` | 集成测试 | Cron 约束在 agent loop 中的集成 (工具阻止/max_iterations/timeout) 测试 |
| `test_vector_integration.py` | 集成测试 | VectorStore (LanceDB 向量搜索) 集成测试 |
| `test_health_check.py` | 单元测试 | HealthMonitor + HealthCheckServer 健康检查测试 |
| `test_wechat_channel.py` | 单元测试 | 微信渠道 (消息收发/白名单) 测试 |
| `test_skill_registry.py` | 单元测试 | SkillRegistry (多目录扫描/原子重载/保护名称) 测试 |
| `test_skill_installer.py` | 单元测试 | SkillInstaller (本地/URL/GitHub/索引安装) 测试 |
| `test_skill_index_client.py` | 单元测试 | IndexClient (索引拉取/缓存/搜索) 测试 |
| `test_skill_integrity.py` | 单元测试 | 技能完整性 (SHA256/SSRF/格式/大小) 测试 |
| `test_skill_tools.py` | 单元测试 | 技能管理工具 (search/install/remove/list/show) 测试 |
| `test_skill_cli.py` | 单元测试 | 技能 CLI 子命令测试 |
| `test_skills_config.py` | 单元测试 | SkillsConfig Pydantic 配置测试 |
| `test_cron_logger.py` | 单元测试 | CronRunLogger (文件创建/追加写入/读取/task_name过滤/limit截断/空文件/不存在文件/JSON格式) 测试 |
