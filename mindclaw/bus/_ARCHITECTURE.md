> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

消息总线层 - asyncio.Queue 双队列，解耦渠道与 Agent。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `events.py` | 核心 | InboundMessage / OutboundMessage 数据类 |
| `queue.py` | 核心 | MessageBus 双队列实现，含消息去重 (5s 窗口) 和限流 (每 session 30条/分钟) |
