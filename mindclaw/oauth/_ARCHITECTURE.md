> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

OAuth 认证层 - 支持 PKCE 流程的 OAuth 2.0 认证，用于 LLM 提供商订阅认证。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `pkce.py` | 工具 | PKCE code_verifier / code_challenge 生成 (S256) |
| `providers.py` | 配置 | 预置 OAuth 提供商配置 (OpenAI Codex 等) |
| `token_store.py` | 核心 | OAuth token 加密持久化 (复用 SecretStore)，含 OAuthTokenInfo 模型 |
| `manager.py` | 核心 | OAuth 流程管理：授权 URL 生成、code 交换、token 自动刷新 |
