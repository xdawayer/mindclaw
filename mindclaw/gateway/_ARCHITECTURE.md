> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

WebSocket Gateway 层 - 远程渠道接入点 (Phase 5 实现)。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空占位 |
| `auth.py` | 核心 | Gateway 认证层：Token 验证 (hmac) + 设备配对管理 (请求/审批/持久化) |
| `server.py` | 核心 | WebSocket 服务器：JSON-RPC 2.0 协议，认证握手 + 设备配对 + 消息收发 + broadcast，ws 身份校验防串线 |
| `channel.py` | 适配 | GatewayChannel：将 GatewayServer 桥接到 BaseChannel 体系 (start/stop/send)，定向发送无 broadcast 回退 |
