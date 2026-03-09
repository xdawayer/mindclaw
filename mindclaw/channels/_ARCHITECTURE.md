> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

渠道层 - 各平台渠道适配，统一接入消息总线。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `base.py` | 核心抽象 | BaseChannel 抽象基类（含 name/send/is_allowed/_handle_message） |
| `cli_channel.py` | 实现 | CLI 终端渠道 (prompt-toolkit + rich)，继承 BaseChannel 统一接口 |
| `manager.py` | 核心 | ChannelManager — 渠道生命周期管理 + 出站消息分发 |
| `telegram.py` | 实现 | TelegramChannel — Telegram 渠道 (polling 模式)，支持群组过滤和白名单 |
