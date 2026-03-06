> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

测试层 - pytest 测试集合。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `test_import.py` | 冒烟测试 | 验证 mindclaw 包可导入 |
| `test_config.py` | 单元测试 | 配置系统 Schema + Loader 测试 |
| `test_llm.py` | 单元测试 | LLM 路由层 (LLMRouter + ChatResult) 测试 |
| `test_bus.py` | 单元测试 | 消息总线 (InboundMessage / OutboundMessage / MessageBus) 测试 |
