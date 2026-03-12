> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

渠道层 - 各平台渠道适配，统一接入消息总线。

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包入口 | 空 |
| `base.py` | 核心抽象 | BaseChannel 抽象基类（含 name/send/is_allowed/_handle_message） |
| `cli_channel.py` | 实现 | CLI 终端渠道 (prompt-toolkit + rich)，继承 BaseChannel 统一接口 |
| `manager.py` | 核心 | ChannelManager — 渠道生命周期管理 + 出站消息分发 |
| `telegram.py` | 实现 | TelegramChannel — Telegram 渠道 (polling 模式)，HTML 富文本发送 + 长消息分段 + 3 次重试，支持群组过滤和白名单 |
| `telegram_format.py` | 工具 | markdown_to_telegram_html() — 标准 Markdown 转 Telegram HTML 格式（安全转义 + 代码块保护） |
| `discord_channel.py` | 实现 | DiscordChannel — Discord 渠道 (discord.py Bot gateway)，支持 DM/服务器消息过滤 |
| `slack.py` | 实现 | SlackChannel — Slack 渠道 (Socket Mode WebSocket)，支持 DM/频道消息过滤，发送时自动转换 Markdown → Slack mrkdwn |
| `slack_format.py` | 工具 | markdown_to_slack() — 标准 Markdown 转 Slack mrkdwn 格式（基于 markdown-to-mrkdwn 库） |
| `feishu.py` | 实现 | FeishuChannel — 飞书渠道 (lark-oapi WebSocket)，支持单聊/群聊过滤 |
| `wechat_channel.py` | 实现 | WeChatChannel — 微信渠道 (Node.js bridge WebSocket)，支持消息解析、群组过滤、白名单 |
