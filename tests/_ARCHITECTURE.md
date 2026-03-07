> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

测试层 - pytest 测试集合。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `test_import.py` | 冒烟测试 | 验证 mindclaw 包可导入 |
| `test_config.py` | 单元测试 | 配置系统 Schema + Loader 测试 |
| `test_llm.py` | 单元测试 | LLM 路由层 (LLMRouter + ChatResult) 测试 |
| `test_bus.py` | 单元测试 | 消息总线 (InboundMessage / OutboundMessage / MessageBus) 测试 |
| `test_agent_loop.py` | 单元测试 | 编排层 Agent Loop (AgentLoop) 测试 |
| `test_cli_channel.py` | 单元测试 | 渠道层 (BaseChannel / CLIChannel) 测试 |
| `test_tools_base.py` | 单元测试 | 工具层 (Tool ABC / RiskLevel / ToolRegistry) 测试 |
| `test_tools_shell.py` | 单元测试 | 工具层 Shell 执行 (ExecTool) 测试 |
| `test_tools_web.py` | 单元测试 | 工具层网页操作 (WebFetchTool 流式抓取 / SSRF 防护 / WebSearchTool) 测试 |
| `test_tools_file_ops.py` | 单元测试 | 工具层文件操作 (ReadFile/WriteFile/EditFile/ListDir + 路径沙箱) 测试 |
| `test_agent_loop_tools.py` | 集成测试 | 编排层 Agent Loop 工具调用集成 (ReAct 循环 + 最大迭代 + 危险工具拦截) 测试 |
| `test_security_sandbox.py` | 单元测试 | 安全层沙箱 (is_command_denied 命令黑名单 / validate_path 路径沙箱) 测试 |
| `test_security_approval.py` | 单元测试 | 安全层审批工作流 (ApprovalManager 审批/拒绝/超时/生命周期) 测试 |
