> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

安全层 - 认证、审批、沙箱等安全原语。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `sandbox.py` | 核心 | 命令黑名单 (is_command_denied) + 路径沙箱验证 (validate_path) |
| `approval.py` | 核心 | 审批工作流 (`ApprovalManager`)，DANGEROUS 工具执行前的用户确认机制；`has_pending(session_key=)` 支持 per-session 查询，阻塞仅限发起会话，其他会话不受影响 |
| `crypto.py` | 核心 | 加密存储 (`SecretStore`)，Fernet 对称加密保存 API Key 等敏感信息，0600 权限 |
