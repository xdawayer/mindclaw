> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

大脑层 - LLM 统一路由，通过 LiteLLM 支持多模型。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `router.py` | 核心 | LLMRouter 统一调用接口 + ChatResult 数据类，含 provider 前缀映射、API Key/OAuth 凭证注入、自动降级和任务级模型路由 |
| `classifier.py` | 工具 | classify_intent() — 零成本关键词意图分类器，将用户消息映射到路由类别 (planning/coding/writing/search/general) |
