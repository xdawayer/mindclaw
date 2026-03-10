# Phase 5 设计文档：Gateway + Telegram

> 日期: 2026-03-09 | 状态: approved

---

## 决策摘要

| 决策 | 选择 |
|------|------|
| 运行模式 | 新增 `mindclaw serve`，与 `chat` 分离 |
| crypto | Phase 5 一并实现（Fernet 加密存储） |
| 设备配对 | 完整实现（跨渠道确认，Telegram 接收配对请求） |
| 现有重构 | `chat` 和 `serve` 统一走 ChannelManager |
| 架构模式 | MindClawApp 编排器（方案 A） |

---

## 1. BaseChannel 增强 + ChannelManager

### BaseChannel 扩展

当前只有 `start()` / `stop()`，补齐 PRD 定义的完整接口：

```python
class BaseChannel(ABC):
    def __init__(self, name: str, bus: MessageBus, allow_from: list[str] | None = None):
        self.name = name          # "cli" / "telegram" / "gateway"
        self.bus = bus
        self.allow_from = set(allow_from) if allow_from else None  # None = 不限制

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到该渠道的具体平台"""

    def is_allowed(self, user_id: str) -> bool:
        """白名单检查。allow_from=None 表示不限（CLI 场景）"""
        if self.allow_from is None:
            return True
        return user_id in self.allow_from

    async def _handle_message(self, text: str, chat_id: str, user_id: str,
                               username: str, **kwargs) -> None:
        """统一入口：白名单检查 -> 构建 InboundMessage -> 投入总线"""
        if not self.is_allowed(user_id):
            return  # 静默丢弃
        msg = InboundMessage(
            channel=self.name, chat_id=chat_id,
            user_id=user_id, username=username, text=text, **kwargs
        )
        await self.bus.put_inbound(msg)
```

CLIChannel 需适配新签名（加 `name="cli"`, 实现 `send()`）。

### ChannelManager

```python
class ChannelManager:
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel

    async def start_all(self) -> None:
        await asyncio.gather(*(ch.start() for ch in self._channels.values()))

    async def stop_all(self) -> None:
        for ch in self._channels.values():
            await ch.stop()

    async def dispatch_outbound(self, msg: OutboundMessage) -> None:
        ch = self._channels.get(msg.channel)
        if ch:
            await ch.send(msg)

    def get(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)
```

职责边界：ChannelManager 只管渠道生命周期 + 出站分发。

---

## 2. MindClawApp 编排器

新增 `mindclaw/app.py`：

```python
class MindClawApp:
    def __init__(self, config: MindClawConfig):
        self.config = config
        self.bus = MessageBus()
        self.router = LLMRouter(config)
        self.channel_manager = ChannelManager(self.bus)
        self.tool_registry = ToolRegistry()
        self.approval_manager = ApprovalManager(bus=self.bus, ...)
        self.session_store = SessionStore(...)
        self.memory_manager = MemoryManager(...)
        self.context_builder = ContextBuilder(...)
        self.agent_loop = AgentLoop(...)

    def _register_tools(self) -> None:
        """注册所有内置工具"""

    def _setup_channels(self, channel_names: list[str]) -> None:
        """根据配置创建并注册渠道"""

    async def _message_router(self) -> None:
        """inbound 队列 -> 配对拦截 -> 审批拦截 -> agent 分发"""

    async def _outbound_router(self) -> None:
        """outbound 队列 -> ChannelManager.dispatch_outbound()"""

    async def run(self, channel_names: list[str]) -> None:
        self._register_tools()
        self._setup_channels(channel_names)
        try:
            await asyncio.gather(
                self.channel_manager.start_all(),
                self._message_router(),
                self._outbound_router(),
            )
        finally:
            await self.channel_manager.stop_all()
```

commands.py 简化为：

```python
async def _run(config_path, channels):
    config = load_config(config_path)
    app = MindClawApp(config)
    await app.run(channels)
```

---

## 3. Gateway WebSocket Server

### gateway/server.py

```python
class GatewayServer:
    def __init__(self, host, port, auth_manager, on_message, on_connect, on_disconnect):
        self._clients: dict[str, WebSocketConnection] = {}

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    async def _handle_connection(self, ws) -> None:
        """连接生命周期：auth -> 配对检查 -> 消息循环 + 心跳"""

    async def send_to_client(self, device_id, message) -> None: ...
    async def broadcast(self, message) -> None: ...
```

### JSON-RPC 协议

```python
# 客户端 -> 服务端
{"jsonrpc": "2.0", "method": "auth", "params": {"token": "xxx", "device_id": "xxx"}, "id": 1}
{"jsonrpc": "2.0", "method": "message", "params": {"text": "你好"}, "id": 2}
{"jsonrpc": "2.0", "method": "ping", "id": 3}

# 服务端 -> 客户端
{"jsonrpc": "2.0", "result": {"status": "authenticated"}, "id": 1}
{"jsonrpc": "2.0", "result": {"status": "pairing_required", "pairing_id": "xxx"}, "id": 1}
{"jsonrpc": "2.0", "method": "reply", "params": {"text": "回复内容"}}
{"jsonrpc": "2.0", "method": "approval_request", "params": {...}}
{"jsonrpc": "2.0", "result": "pong", "id": 3}
```

### GatewayChannel

```python
class GatewayChannel(BaseChannel):
    def __init__(self, bus, server: GatewayServer):
        super().__init__(name="gateway", bus=bus)
        self.server = server

    async def start(self) -> None:
        await self.server.start()

    async def stop(self) -> None:
        await self.server.stop()

    async def send(self, msg: OutboundMessage) -> None:
        await self.server.broadcast({"method": "reply", "params": {"text": msg.text}})
```

心跳间隔 30 秒，3 次未响应断开。

---

## 4. Gateway 认证 + 设备配对

### gateway/auth.py

```python
class GatewayAuthManager:
    def __init__(self, token: str, paired_devices_path: Path):
        self._token = token
        self._paired: dict[str, PairedDevice]
        self._pending_pairings: dict[str, PairingRequest]

    def verify_token(self, token: str) -> bool:
        """hmac.compare_digest 防时序攻击"""

    def is_paired(self, device_id: str) -> bool: ...

    async def request_pairing(self, device_id, device_name, notify_callback) -> str:
        """发起配对，通过 callback 通知已认证渠道（如 Telegram）"""

    async def await_pairing(self, pairing_id, timeout=300) -> bool:
        """等待用户确认配对"""

    def resolve_pairing(self, pairing_id, approved) -> None:
        """由消息路由调用（用户回复 'pair xxx'）"""

    def _save_devices(self) -> None:
        """持久化到 JSON（0600 权限）"""

    def _load_devices(self) -> None: ...
```

### 配对消息路由

MindClawApp._message_router 增加配对拦截（优先级在审批之前）：

```
msg -> 配对回复? ("pair/reject xxx") -> resolve_pairing()
    -> 审批回复? ("yes/no")          -> approval_manager.resolve()
    -> 正常消息                      -> agent 分发
```

### Token 生成

- 首次启动 `secrets.token_urlsafe(32)` 自动生成
- 存储 `data/gateway_token`（0600）
- 可通过 config / `$MINDCLAW_GATEWAY_TOKEN` 覆盖

设备配对数据：`data/paired_devices.json`（0600）

---

## 5. Telegram Channel

### channels/telegram.py

```python
class TelegramChannel(BaseChannel):
    def __init__(self, bus, token, allow_from=None, allow_groups=False):
        super().__init__(name="telegram", bus=bus, allow_from=allow_from)
        self.allow_groups = allow_groups

    async def start(self) -> None:
        """ApplicationBuilder -> MessageHandler -> start_polling()"""

    async def stop(self) -> None:
        """updater.stop -> app.stop -> app.shutdown"""

    async def send(self, msg: OutboundMessage) -> None:
        """bot.send_message(chat_id, text, parse_mode='Markdown')"""

    async def _on_message(self, update, context) -> None:
        """群组过滤 -> BaseChannel._handle_message()"""
```

设计要点：
- **Polling 而非 Webhook** — 个人使用，无需公网域名
- **python-telegram-bot v20+** — 原生 asyncio
- **白名单用 user_id**（数字），不用 username（可变）

---

## 6. SecretStore 加密存储

### security/crypto.py

```python
class SecretStore:
    def __init__(self, store_path: Path, master_key_path: Path):
        """Fernet 对称加密"""

    def init_or_load_key(self) -> None:
        """首次生成 master key（0600），后续加载"""

    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...
    def list_keys(self) -> list[str]: ...
```

配置加载优先级：`环境变量 > 加密存储 > 原始值`

CLI 命令：`mindclaw secret-set/secret-list/secret-delete`

文件布局：

```
data/
├── master.key           # Fernet key（0600）
├── secrets.enc          # 加密密钥存储（0600）
├── paired_devices.json  # 设备配对（0600）
└── gateway_token        # Gateway Token（0600）
```

---

## 7. CLI 命令重构

```python
@app.command()
def chat(...):       # mindclaw chat → MindClawApp(["cli"])

@app.command()
def serve(...):      # mindclaw serve → MindClawApp(["gateway", "telegram"])

@app.command()
def secret_set(...)  # mindclaw secret-set NAME VALUE

@app.command()
def secret_list()    # mindclaw secret-list

@app.command()
def secret_delete()  # mindclaw secret-delete NAME

@app.command()
def version()        # mindclaw version
```

---

## 8. 文件变更总览

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `mindclaw/app.py` | MindClawApp 编排器 |
| 新增 | `mindclaw/channels/manager.py` | ChannelManager |
| 新增 | `mindclaw/channels/telegram.py` | Telegram 渠道 |
| 新增 | `mindclaw/gateway/server.py` | WebSocket Server |
| 新增 | `mindclaw/gateway/auth.py` | Token + 设备配对 |
| 新增 | `mindclaw/security/crypto.py` | SecretStore 加密存储 |
| 修改 | `mindclaw/channels/base.py` | 扩展 send/is_allowed/_handle_message |
| 修改 | `mindclaw/channels/cli_channel.py` | 适配新 BaseChannel 签名 |
| 修改 | `mindclaw/config/schema.py` | 新增 ChannelConfig |
| 修改 | `mindclaw/config/loader.py` | 集成 SecretStore |
| 修改 | `mindclaw/cli/commands.py` | chat/serve + secret 命令 |

注：`security/auth.py` 的白名单职责已集成到 BaseChannel.is_allowed()，无需独立文件。

## 9. 新增依赖

```
websockets
python-telegram-bot
cryptography
```
