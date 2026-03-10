# Phase 5: Gateway + Telegram Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable remote access to MindClaw via WebSocket Gateway and Telegram, with encrypted secret storage and unified app orchestration.

**Architecture:** MindClawApp orchestrator coordinates ChannelManager (channel lifecycle + outbound dispatch), message routing (pairing/approval/agent), and all existing components. BaseChannel enhanced with send/is_allowed/_handle_message. Gateway uses JSON-RPC over WebSocket with token auth + device pairing. Telegram uses polling via python-telegram-bot.

**Tech Stack:** websockets, python-telegram-bot v20+, cryptography (Fernet)

**Design doc:** `docs/plans/2026-03-09-phase5-gateway-telegram-design.md`

---

### Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml:6-15`

**Step 1: Add new dependencies to pyproject.toml**

Add `python-telegram-bot` and `cryptography` to the dependencies list. Note: `websockets` is already listed.

```toml
dependencies = [
    "litellm>=1.55",
    "pydantic>=2.0",
    "typer>=0.15",
    "rich>=13.0",
    "prompt-toolkit>=3.0",
    "httpx>=0.28",
    "loguru>=0.7",
    "websockets>=14.0",
    "python-telegram-bot>=21.0",
    "cryptography>=44.0",
]
```

**Step 2: Install dependencies**

Run: `cd /Users/wzb/Documents/mindclaw && uv sync`
Expected: All dependencies installed successfully.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(phase5): add python-telegram-bot and cryptography dependencies"
```

---

### Task 2: Config Schema Extension

**Files:**
- Modify: `mindclaw/config/schema.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_channel_config_defaults():
    from mindclaw.config.schema import ChannelConfig

    cc = ChannelConfig()
    assert cc.enabled is True
    assert cc.token == ""
    assert cc.allow_from == []
    assert cc.allow_groups is False


def test_channel_config_from_camel_case():
    from mindclaw.config.schema import ChannelConfig

    cc = ChannelConfig(**{"allowFrom": ["123"], "allowGroups": True, "token": "tok"})
    assert cc.allow_from == ["123"]
    assert cc.allow_groups is True
    assert cc.token == "tok"


def test_mindclaw_config_has_channels():
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert config.channels == {}


def test_mindclaw_config_channels_from_dict():
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig(**{
        "channels": {
            "telegram": {"token": "bot123", "allowFrom": ["111"], "allowGroups": False}
        }
    })
    assert "telegram" in config.channels
    assert config.channels["telegram"].token == "bot123"
    assert config.channels["telegram"].allow_from == ["111"]


def test_gateway_config_has_token():
    from mindclaw.config.schema import GatewayConfig

    gc = GatewayConfig()
    assert gc.token == ""


def test_security_config_has_pairing_timeout():
    from mindclaw.config.schema import SecurityConfig

    sc = SecurityConfig()
    assert sc.pairing_timeout == 300
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_config.py -v -x`
Expected: FAIL — `ChannelConfig` not found.

**Step 3: Implement ChannelConfig + update MindClawConfig**

In `mindclaw/config/schema.py`, add `ChannelConfig` class and update `GatewayConfig`, `SecurityConfig`, and `MindClawConfig`:

```python
class ChannelConfig(BaseModel):
    enabled: bool = True
    token: str = ""
    allow_from: list[str] = Field(default_factory=list, alias="allowFrom")
    allow_groups: bool = Field(default=False, alias="allowGroups")

    model_config = {"populate_by_name": True}
```

Add `token` field to `GatewayConfig`:

```python
class GatewayConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""

    model_config = {"populate_by_name": True}
```

Add `pairing_timeout` field to `SecurityConfig`:

```python
class SecurityConfig(BaseModel):
    approval_timeout: int = Field(default=300, alias="approvalTimeout")
    pairing_timeout: int = Field(default=300, alias="pairingTimeout")
    session_poisoning_protection: bool = Field(
        default=True, alias="sessionPoisoningProtection"
    )

    model_config = {"populate_by_name": True}
```

Add `channels` field to `MindClawConfig`:

```python
class MindClawConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)

    model_config = {"populate_by_name": True}
```

Update the file header comment to include `ChannelConfig` in the exports.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Run full test suite to check for regressions**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v`
Expected: ALL PASS (existing tests should not break)

**Step 6: Commit**

```bash
git add mindclaw/config/schema.py tests/test_config.py
git commit -m "feat(phase5): add ChannelConfig, gateway token, and pairing timeout to config schema"
```

---

### Task 3: SecretStore (crypto.py)

**Files:**
- Create: `mindclaw/security/crypto.py`
- Test: `tests/test_crypto.py`

**Step 1: Write the failing tests**

Create `tests/test_crypto.py`:

```python
# input: mindclaw.security.crypto
# output: SecretStore 加密存储测试
# pos: 安全层加密存储测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


def test_secret_store_init_creates_master_key(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    assert (tmp_path / "master.key").exists()
    # Check 0600 permissions (owner read/write only)
    mode = (tmp_path / "master.key").stat().st_mode & 0o777
    assert mode == 0o600


def test_secret_store_set_and_get(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("API_KEY", "sk-test-123")
    assert store.get("API_KEY") == "sk-test-123"


def test_secret_store_get_nonexistent(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    assert store.get("NONEXISTENT") is None


def test_secret_store_delete(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("KEY", "value")
    store.delete("KEY")
    assert store.get("KEY") is None


def test_secret_store_list_keys(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("A", "1")
    store.set("B", "2")
    keys = store.list_keys()
    assert sorted(keys) == ["A", "B"]


def test_secret_store_persistence(tmp_path):
    """Secrets should survive creating a new SecretStore instance."""
    from mindclaw.security.crypto import SecretStore

    store1 = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store1.init_or_load_key()
    store1.set("PERSIST", "hello")

    store2 = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store2.init_or_load_key()
    assert store2.get("PERSIST") == "hello"


def test_secret_store_file_permissions(tmp_path):
    from mindclaw.security.crypto import SecretStore

    store = SecretStore(
        store_path=tmp_path / "secrets.enc",
        master_key_path=tmp_path / "master.key",
    )
    store.init_or_load_key()
    store.set("KEY", "val")
    mode = (tmp_path / "secrets.enc").stat().st_mode & 0o777
    assert mode == 0o600
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_crypto.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement SecretStore**

Create `mindclaw/security/crypto.py`:

```python
# input: cryptography (Fernet), json, pathlib
# output: 导出 SecretStore
# pos: 安全层加密存储，使用 Fernet 对称加密保存 API Key 等敏感信息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from pathlib import Path

from cryptography.fernet import Fernet


class SecretStore:
    """Encrypted storage for sensitive values (API keys, tokens, etc.).

    Uses Fernet symmetric encryption. Master key is stored in a separate file
    with 0600 permissions. The encrypted secrets file is also 0600.
    """

    def __init__(self, store_path: Path, master_key_path: Path) -> None:
        self._store_path = store_path
        self._master_key_path = master_key_path
        self._fernet: Fernet | None = None

    def init_or_load_key(self) -> None:
        """Load existing master key or generate a new one (0600 permissions)."""
        if self._master_key_path.exists():
            key = self._master_key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self._master_key_path.parent.mkdir(parents=True, exist_ok=True)
            self._master_key_path.write_bytes(key)
            self._master_key_path.chmod(0o600)
        self._fernet = Fernet(key)

    def get(self, name: str) -> str | None:
        """Retrieve a secret by name. Returns None if not found."""
        secrets = self._load_all()
        return secrets.get(name)

    def set(self, name: str, value: str) -> None:
        """Store a secret (overwrites if exists)."""
        secrets = self._load_all()
        secrets[name] = value
        self._save_all(secrets)

    def delete(self, name: str) -> None:
        """Remove a secret by name. No-op if not found."""
        secrets = self._load_all()
        secrets.pop(name, None)
        self._save_all(secrets)

    def list_keys(self) -> list[str]:
        """List all stored secret names (not values)."""
        return list(self._load_all().keys())

    def _load_all(self) -> dict[str, str]:
        if not self._store_path.exists():
            return {}
        encrypted = self._store_path.read_bytes()
        decrypted = self._fernet.decrypt(encrypted)
        return json.loads(decrypted)

    def _save_all(self, secrets: dict[str, str]) -> None:
        raw = json.dumps(secrets).encode()
        encrypted = self._fernet.encrypt(raw)
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_bytes(encrypted)
        self._store_path.chmod(0o600)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_crypto.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add mindclaw/security/crypto.py tests/test_crypto.py
git commit -m "feat(phase5): add SecretStore with Fernet encrypted storage"
```

---

### Task 4: BaseChannel Enhancement + CLIChannel Adaptation

**Files:**
- Modify: `mindclaw/channels/base.py`
- Modify: `mindclaw/channels/cli_channel.py`
- Modify: `tests/test_cli_channel.py`

**Step 1: Write the failing tests**

Replace contents of `tests/test_cli_channel.py`:

```python
# input: mindclaw.channels
# output: BaseChannel + CLIChannel 测试
# pos: 渠道层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_base_channel_is_abstract():
    """BaseChannel 应该是抽象类，不能直接实例化"""
    from mindclaw.channels.base import BaseChannel

    with pytest.raises(TypeError):
        BaseChannel(name="test", bus=MessageBus())


def test_base_channel_is_allowed_no_whitelist():
    """allow_from=None 时任何用户都允许"""
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    ch = DummyChannel(name="dummy", bus=MessageBus(), allow_from=None)
    assert ch.is_allowed("anyone") is True


def test_base_channel_is_allowed_with_whitelist():
    """allow_from 设置时只有白名单中的用户允许"""
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    ch = DummyChannel(name="dummy", bus=MessageBus(), allow_from=["user1", "user2"])
    assert ch.is_allowed("user1") is True
    assert ch.is_allowed("user3") is False


@pytest.mark.asyncio
async def test_base_channel_handle_message_allowed():
    """_handle_message 应将允许的消息放入总线"""
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    bus = MessageBus()
    ch = DummyChannel(name="test", bus=bus)
    await ch._handle_message(text="hello", chat_id="c1", user_id="u1", username="alice")
    msg = await bus.get_inbound()
    assert msg.channel == "test"
    assert msg.text == "hello"
    assert msg.user_id == "u1"


@pytest.mark.asyncio
async def test_base_channel_handle_message_blocked():
    """_handle_message 应静默丢弃不在白名单中的用户消息"""
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    bus = MessageBus()
    ch = DummyChannel(name="test", bus=bus, allow_from=["user1"])
    await ch._handle_message(text="hello", chat_id="c1", user_id="bad_user", username="bob")
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_cli_channel_creates_inbound_message():
    """CLIChannel 应将用户输入转为 InboundMessage 并放入总线"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)
    assert channel.name == "cli"

    await channel._handle_input("hello world")

    msg = await bus.get_inbound()
    assert msg.channel == "cli"
    assert msg.chat_id == "local"
    assert msg.text == "hello world"


@pytest.mark.asyncio
async def test_cli_channel_send():
    """CLIChannel.send() 应不抛异常（输出到 Rich console）"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)
    outbound = OutboundMessage(channel="cli", chat_id="local", text="reply text")
    # Should not raise
    await channel.send(outbound)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_cli_channel.py -v -x`
Expected: FAIL — BaseChannel() signature mismatch (missing `name` param).

**Step 3: Update BaseChannel**

Replace `mindclaw/channels/base.py`:

```python
# input: abc, bus/queue.py, bus/events.py
# output: 导出 BaseChannel
# pos: 渠道层抽象基类，所有渠道的统一接口（含白名单 + 统一消息入口）
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus


class BaseChannel(ABC):
    def __init__(
        self,
        name: str,
        bus: MessageBus,
        allow_from: list[str] | None = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.allow_from = set(allow_from) if allow_from else None

    @abstractmethod
    async def start(self) -> None:
        """Start the channel."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel."""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through this channel's platform."""

    def is_allowed(self, user_id: str) -> bool:
        """Check if user_id is in the whitelist. None means allow all."""
        if self.allow_from is None:
            return True
        return user_id in self.allow_from

    async def _handle_message(
        self,
        text: str,
        chat_id: str,
        user_id: str,
        username: str,
        **kwargs,
    ) -> None:
        """Unified inbound handler: whitelist check -> build InboundMessage -> enqueue."""
        if not self.is_allowed(user_id):
            return
        msg = InboundMessage(
            channel=self.name,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            text=text,
            **kwargs,
        )
        await self.bus.put_inbound(msg)
```

**Step 4: Update CLIChannel for new BaseChannel signature**

Replace `mindclaw/channels/cli_channel.py`:

```python
# input: channels/base.py, bus/events.py, prompt_toolkit, rich
# output: 导出 CLIChannel
# pos: CLI 渠道实现，本地终端交互
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import os

from rich.console import Console
from rich.markdown import Markdown

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel

console = Console()


class CLIChannel(BaseChannel):
    def __init__(self, bus: MessageBus) -> None:
        super().__init__(name="cli", bus=bus, allow_from=None)
        self._running = False
        self._stop_event: asyncio.Event | None = None

    async def _handle_input(self, text: str) -> None:
        await self._handle_message(
            text=text,
            chat_id="local",
            user_id=os.getenv("USER", "user"),
            username=os.getenv("USER", "user"),
        )

    async def send(self, msg: OutboundMessage) -> None:
        """Print reply to terminal via Rich Markdown."""
        console.print()
        console.print(Markdown(msg.text))
        console.print()

    async def _input_loop(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout

        session = PromptSession()
        with patch_stdout():
            while self._running:
                try:
                    text = await session.prompt_async("You> ")
                    text = text.strip()
                    if not text:
                        continue
                    if text.lower() in ("exit", "quit", "/quit"):
                        self._running = False
                        self._stop_event.set()
                        break
                    await self._handle_input(text)
                except (EOFError, KeyboardInterrupt):
                    self._running = False
                    self._stop_event.set()
                    break

    async def _output_loop(self) -> None:
        while not self._stop_event.is_set():
            get_task = asyncio.ensure_future(self.bus.get_outbound())
            stop_task = asyncio.ensure_future(self._stop_event.wait())
            done, pending = await asyncio.wait(
                {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if get_task in done:
                msg = get_task.result()
                await self.send(msg)

    async def start(self) -> None:
        self._running = True
        self._stop_event = asyncio.Event()
        console.print("[bold green]MindClaw[/] ready. Type 'exit' to quit.\n")
        await asyncio.gather(self._input_loop(), self._output_loop())

    async def stop(self) -> None:
        self._running = False
        if self._stop_event:
            self._stop_event.set()
```

**Step 5: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_cli_channel.py -v`
Expected: ALL PASS

**Step 6: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v`
Expected: ALL PASS (no regressions)

**Step 7: Commit**

```bash
git add mindclaw/channels/base.py mindclaw/channels/cli_channel.py tests/test_cli_channel.py
git commit -m "feat(phase5): enhance BaseChannel with send/is_allowed/_handle_message, adapt CLIChannel"
```

---

### Task 5: ChannelManager

**Files:**
- Create: `mindclaw/channels/manager.py`
- Test: `tests/test_channel_manager.py`

**Step 1: Write the failing tests**

Create `tests/test_channel_manager.py`:

```python
# input: mindclaw.channels.manager
# output: ChannelManager 测试
# pos: 渠道管理器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.base import BaseChannel


class FakeChannel(BaseChannel):
    def __init__(self, name: str, bus: MessageBus):
        super().__init__(name=name, bus=bus)
        self.started = False
        self.stopped = False
        self.sent: list[OutboundMessage] = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, msg: OutboundMessage):
        self.sent.append(msg)


def test_channel_manager_register_and_get():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel("test", bus)
    mgr.register(ch)
    assert mgr.get("test") is ch
    assert mgr.get("nonexistent") is None


@pytest.mark.asyncio
async def test_channel_manager_start_stop_all():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch1 = FakeChannel("a", bus)
    ch2 = FakeChannel("b", bus)
    mgr.register(ch1)
    mgr.register(ch2)

    await mgr.start_all()
    assert ch1.started and ch2.started

    await mgr.stop_all()
    assert ch1.stopped and ch2.stopped


@pytest.mark.asyncio
async def test_channel_manager_dispatch_outbound():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel("telegram", bus)
    mgr.register(ch)

    msg = OutboundMessage(channel="telegram", chat_id="123", text="hello")
    await mgr.dispatch_outbound(msg)
    assert len(ch.sent) == 1
    assert ch.sent[0].text == "hello"


@pytest.mark.asyncio
async def test_channel_manager_dispatch_unknown_channel():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    msg = OutboundMessage(channel="nonexistent", chat_id="123", text="hello")
    # Should not raise
    await mgr.dispatch_outbound(msg)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_channel_manager.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement ChannelManager**

Create `mindclaw/channels/manager.py`:

```python
# input: asyncio, channels/base.py, bus/queue.py, bus/events.py
# output: 导出 ChannelManager
# pos: 渠道管理器，负责渠道生命周期和出站消息分发
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class ChannelManager:
    """Manages channel lifecycle and outbound message dispatch."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel
        logger.info(f"Channel registered: {channel.name}")

    async def start_all(self) -> None:
        """Start all registered channels concurrently."""
        if not self._channels:
            return
        await asyncio.gather(*(ch.start() for ch in self._channels.values()))

    async def stop_all(self) -> None:
        """Stop all registered channels."""
        for name, ch in self._channels.items():
            try:
                await ch.stop()
            except Exception:
                logger.exception(f"Error stopping channel {name}")

    async def dispatch_outbound(self, msg: OutboundMessage) -> None:
        """Route an outbound message to the appropriate channel's send()."""
        ch = self._channels.get(msg.channel)
        if ch is None:
            logger.warning(f"No channel found for outbound message: {msg.channel}")
            return
        await ch.send(msg)

    def get(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)
```

**Step 4: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_channel_manager.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add mindclaw/channels/manager.py tests/test_channel_manager.py
git commit -m "feat(phase5): add ChannelManager for channel lifecycle and outbound dispatch"
```

---

### Task 6: GatewayAuthManager

**Files:**
- Create: `mindclaw/gateway/auth.py`
- Test: `tests/test_gateway_auth.py`

**Step 1: Write the failing tests**

Create `tests/test_gateway_auth.py`:

```python
# input: mindclaw.gateway.auth
# output: GatewayAuthManager 测试
# pos: Gateway 认证 + 设备配对测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

import pytest


def test_verify_token_correct(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="secret123", paired_devices_path=tmp_path / "devices.json")
    assert mgr.verify_token("secret123") is True


def test_verify_token_incorrect(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="secret123", paired_devices_path=tmp_path / "devices.json")
    assert mgr.verify_token("wrong") is False


def test_is_paired_initially_empty(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    assert mgr.is_paired("device1") is False


@pytest.mark.asyncio
async def test_pairing_approved(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    notifications = []

    async def notify(text):
        notifications.append(text)

    async def approve():
        await asyncio.sleep(0.05)
        pairing_id = list(mgr._pending_pairings.keys())[0]
        mgr.resolve_pairing(pairing_id, approved=True)

    asyncio.create_task(approve())
    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=5.0)

    assert result is True
    assert mgr.is_paired("dev1")
    assert len(notifications) == 1
    assert "dev1" in notifications[0] or "My Phone" in notifications[0]


@pytest.mark.asyncio
async def test_pairing_rejected(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")

    async def notify(text):
        pass

    async def reject():
        await asyncio.sleep(0.05)
        pairing_id = list(mgr._pending_pairings.keys())[0]
        mgr.resolve_pairing(pairing_id, approved=False)

    asyncio.create_task(reject())
    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=5.0)

    assert result is False
    assert not mgr.is_paired("dev1")


@pytest.mark.asyncio
async def test_pairing_timeout(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")

    async def notify(text):
        pass

    pairing_id = await mgr.request_pairing("dev1", "My Phone", notify)
    result = await mgr.await_pairing(pairing_id, timeout=0.1)

    assert result is False
    assert not mgr.is_paired("dev1")


def test_pairing_persistence(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    import time

    devices_path = tmp_path / "devices.json"
    mgr1 = GatewayAuthManager(token="t", paired_devices_path=devices_path)
    mgr1._paired["dev1"] = PairedDevice(
        device_id="dev1", device_name="Phone",
        paired_at=time.time(), last_seen=time.time(),
    )
    mgr1._save_devices()

    mgr2 = GatewayAuthManager(token="t", paired_devices_path=devices_path)
    assert mgr2.is_paired("dev1")


def test_resolve_pairing_unknown_id(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager

    mgr = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "devices.json")
    # Should not raise
    mgr.resolve_pairing("nonexistent", approved=True)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_gateway_auth.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement GatewayAuthManager**

Create `mindclaw/gateway/auth.py`:

```python
# input: asyncio, hmac, json, uuid, time, pathlib
# output: 导出 GatewayAuthManager, PairedDevice, PairingRequest
# pos: Gateway 认证层，Token 验证 + 设备配对管理
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import hmac
import json
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    paired_at: float
    last_seen: float


@dataclass
class PairingRequest:
    pairing_id: str
    device_id: str
    device_name: str
    created_at: float = field(default_factory=time.time)
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False


class GatewayAuthManager:
    """Token authentication and device pairing for Gateway WebSocket connections."""

    def __init__(self, token: str, paired_devices_path: Path) -> None:
        self._token = token
        self._paired_devices_path = paired_devices_path
        self._paired: dict[str, PairedDevice] = {}
        self._pending_pairings: dict[str, PairingRequest] = {}
        self._load_devices()

    def verify_token(self, token: str) -> bool:
        """Layer 1: Constant-time token comparison."""
        return hmac.compare_digest(self._token, token)

    def is_paired(self, device_id: str) -> bool:
        """Layer 2: Check if device has been paired."""
        return device_id in self._paired

    def update_last_seen(self, device_id: str) -> None:
        """Update last_seen timestamp for a paired device."""
        if device_id in self._paired:
            self._paired[device_id].last_seen = time.time()

    async def request_pairing(
        self,
        device_id: str,
        device_name: str,
        notify_callback: Callable[[str], Coroutine[Any, Any, None]],
    ) -> str:
        """Initiate pairing. Sends notification via callback. Returns pairing_id."""
        pairing_id = f"pair_{uuid.uuid4().hex[:8]}"
        self._pending_pairings[pairing_id] = PairingRequest(
            pairing_id=pairing_id,
            device_id=device_id,
            device_name=device_name,
        )
        logger.info(f"Pairing requested: {pairing_id} for device '{device_name}' ({device_id})")
        await notify_callback(
            f"New device pairing request:\n"
            f"  Device: {device_name}\n"
            f"  ID: {device_id}\n\n"
            f"Reply 'pair {pairing_id}' to approve, 'reject {pairing_id}' to deny."
        )
        return pairing_id

    async def await_pairing(self, pairing_id: str, timeout: float = 300.0) -> bool:
        """Wait for user to approve/reject pairing via an authenticated channel."""
        req = self._pending_pairings.get(pairing_id)
        if req is None:
            return False
        try:
            await asyncio.wait_for(req.event.wait(), timeout=timeout)
            if req.approved:
                self._paired[req.device_id] = PairedDevice(
                    device_id=req.device_id,
                    device_name=req.device_name,
                    paired_at=time.time(),
                    last_seen=time.time(),
                )
                self._save_devices()
                logger.info(f"Device paired: {req.device_id}")
            return req.approved
        except asyncio.TimeoutError:
            logger.warning(f"Pairing timeout: {pairing_id}")
            return False
        finally:
            self._pending_pairings.pop(pairing_id, None)

    def resolve_pairing(self, pairing_id: str, approved: bool) -> None:
        """Called by message router when user replies 'pair xxx' or 'reject xxx'."""
        req = self._pending_pairings.get(pairing_id)
        if req is None:
            return
        req.approved = approved
        req.event.set()

    def is_pairing_reply(self, text: str) -> bool:
        """Check if text matches 'pair <id>' or 'reject <id>' pattern."""
        parts = text.strip().lower().split()
        if len(parts) != 2:
            return False
        cmd, pairing_id = parts
        if cmd not in ("pair", "reject"):
            return False
        return pairing_id in self._pending_pairings

    def handle_pairing_reply(self, text: str) -> None:
        """Parse and resolve a pairing reply."""
        parts = text.strip().lower().split()
        if len(parts) != 2:
            return
        cmd, pairing_id = parts
        self.resolve_pairing(pairing_id, approved=(cmd == "pair"))

    def _save_devices(self) -> None:
        data = {
            did: {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "paired_at": d.paired_at,
                "last_seen": d.last_seen,
            }
            for did, d in self._paired.items()
        }
        self._paired_devices_path.parent.mkdir(parents=True, exist_ok=True)
        self._paired_devices_path.write_text(json.dumps(data, indent=2))
        self._paired_devices_path.chmod(0o600)

    def _load_devices(self) -> None:
        if not self._paired_devices_path.exists():
            return
        try:
            data = json.loads(self._paired_devices_path.read_text())
            for did, info in data.items():
                self._paired[did] = PairedDevice(**info)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to load paired devices, starting fresh")
```

**Step 4: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_gateway_auth.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add mindclaw/gateway/auth.py tests/test_gateway_auth.py
git commit -m "feat(phase5): add GatewayAuthManager with token auth and device pairing"
```

---

### Task 7: GatewayServer + GatewayChannel

**Files:**
- Create: `mindclaw/gateway/server.py`
- Create: `mindclaw/gateway/channel.py`
- Test: `tests/test_gateway_server.py`

**Step 1: Write the failing tests**

Create `tests/test_gateway_server.py`:

```python
# input: mindclaw.gateway
# output: GatewayServer + GatewayChannel 测试
# pos: Gateway 层集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

import pytest
import websockets

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_gateway_server_auth_success(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.server import GatewayServer
    import time

    messages_received = []

    async def on_message(device_id, text):
        messages_received.append((device_id, text))

    auth = GatewayAuthManager(token="test-token", paired_devices_path=tmp_path / "d.json")
    # Pre-pair a device
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=on_message,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Auth
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "test-token", "device_id": "dev1"}, "id": 1
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"]["status"] == "authenticated"

            # Send message
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "message",
                "params": {"text": "hello"}, "id": 2
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"]["status"] == "ok"

        # Wait for on_message callback
        await asyncio.sleep(0.1)
        assert ("dev1", "hello") in messages_received
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_server_auth_wrong_token(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="correct", paired_devices_path=tmp_path / "d.json")
    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "wrong", "device_id": "dev1"}, "id": 1
            }))
            resp = json.loads(await ws.recv())
            assert "error" in resp
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_server_ping_pong(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.server import GatewayServer
    import time

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "t", "device_id": "dev1"}, "id": 1
            }))
            await ws.recv()

            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "ping", "id": 99
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"] == "pong"
            assert resp["id"] == 99
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_channel_send(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.channel import GatewayChannel
    from mindclaw.gateway.server import GatewayServer
    import time

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    bus = MessageBus()
    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    channel = GatewayChannel(bus=bus, server=server)
    await channel.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Auth
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "t", "device_id": "dev1"}, "id": 1
            }))
            await ws.recv()

            # Server sends outbound
            out = OutboundMessage(channel="gateway", chat_id="dev1", text="reply!")
            await channel.send(out)

            resp = json.loads(await ws.recv())
            assert resp["method"] == "reply"
            assert resp["params"]["text"] == "reply!"
    finally:
        await channel.stop()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_gateway_server.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement GatewayServer**

Create `mindclaw/gateway/server.py`:

```python
# input: websockets, asyncio, json, gateway/auth.py
# output: 导出 GatewayServer
# pos: WebSocket Server，为自有客户端提供 JSON-RPC 接入点
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import websockets
from loguru import logger

from .auth import GatewayAuthManager


def _jsonrpc_result(result: Any, msg_id: int | str | None) -> str:
    return json.dumps({"jsonrpc": "2.0", "result": result, "id": msg_id})


def _jsonrpc_error(code: int, message: str, msg_id: int | str | None) -> str:
    return json.dumps({"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": msg_id})


def _jsonrpc_notification(method: str, params: dict) -> str:
    return json.dumps({"jsonrpc": "2.0", "method": method, "params": params})


class GatewayServer:
    """WebSocket server for self-hosted clients (CLI-over-WS, Web UI, native apps)."""

    def __init__(
        self,
        host: str,
        port: int,
        auth_manager: GatewayAuthManager,
        on_message: Callable[[str, str], Coroutine[Any, Any, None] | None],
    ) -> None:
        self.host = host
        self._requested_port = port
        self.port: int = port  # Actual port after start (may differ if port=0)
        self.auth_manager = auth_manager
        self._on_message = on_message
        self._server: websockets.WebSocketServer | None = None
        self._clients: dict[str, websockets.WebSocketServerProtocol] = {}  # device_id -> ws

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handle_connection, self.host, self._requested_port,
        )
        # Resolve actual port (important when port=0 for tests)
        for sock in self._server.sockets:
            self.port = sock.getsockname()[1]
            break
        logger.info(f"Gateway listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._clients.clear()
            logger.info("Gateway stopped")

    async def send_to_client(self, device_id: str, message: dict) -> None:
        ws = self._clients.get(device_id)
        if ws is None:
            return
        try:
            await ws.send(_jsonrpc_notification(message.get("method", "reply"), message.get("params", {})))
        except websockets.ConnectionClosed:
            self._clients.pop(device_id, None)

    async def broadcast(self, message: dict) -> None:
        disconnected = []
        for device_id, ws in self._clients.items():
            try:
                await ws.send(_jsonrpc_notification(message.get("method", "reply"), message.get("params", {})))
            except websockets.ConnectionClosed:
                disconnected.append(device_id)
        for did in disconnected:
            self._clients.pop(did, None)

    async def _handle_connection(self, ws: websockets.WebSocketServerProtocol) -> None:
        device_id: str | None = None
        try:
            # First message must be auth
            raw = await asyncio.wait_for(ws.recv(), timeout=30.0)
            msg = json.loads(raw)
            method = msg.get("method")
            params = msg.get("params", {})
            msg_id = msg.get("id")

            if method != "auth":
                await ws.send(_jsonrpc_error(-32600, "First message must be auth", msg_id))
                return

            token = params.get("token", "")
            device_id = params.get("device_id", "")

            if not self.auth_manager.verify_token(token):
                await ws.send(_jsonrpc_error(-32001, "Invalid token", msg_id))
                return

            if not self.auth_manager.is_paired(device_id):
                await ws.send(_jsonrpc_result({"status": "pairing_required"}, msg_id))
                return

            await ws.send(_jsonrpc_result({"status": "authenticated"}, msg_id))
            self._clients[device_id] = ws
            self.auth_manager.update_last_seen(device_id)
            logger.info(f"Gateway client authenticated: {device_id}")

            # Message loop
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send(_jsonrpc_error(-32700, "Parse error", None))
                    continue

                method = msg.get("method")
                params = msg.get("params", {})
                msg_id = msg.get("id")

                if method == "ping":
                    await ws.send(_jsonrpc_result("pong", msg_id))
                elif method == "message":
                    text = params.get("text", "")
                    if text:
                        result = self._on_message(device_id, text)
                        if asyncio.iscoroutine(result):
                            await result
                    await ws.send(_jsonrpc_result({"status": "ok"}, msg_id))
                else:
                    await ws.send(_jsonrpc_error(-32601, f"Unknown method: {method}", msg_id))

        except asyncio.TimeoutError:
            logger.debug("Gateway client auth timeout")
        except websockets.ConnectionClosed:
            pass
        except Exception:
            logger.exception("Gateway connection error")
        finally:
            if device_id:
                self._clients.pop(device_id, None)
                logger.debug(f"Gateway client disconnected: {device_id}")
```

**Step 4: Implement GatewayChannel**

Create `mindclaw/gateway/channel.py`:

```python
# input: channels/base.py, gateway/server.py, bus/events.py
# output: 导出 GatewayChannel
# pos: Gateway 渠道适配器，桥接 GatewayServer 与消息总线
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.base import BaseChannel

from .server import GatewayServer


class GatewayChannel(BaseChannel):
    """Bridges GatewayServer WebSocket connections to the MessageBus."""

    def __init__(self, bus: MessageBus, server: GatewayServer) -> None:
        super().__init__(name="gateway", bus=bus, allow_from=None)
        self.server = server

    async def start(self) -> None:
        await self.server.start()

    async def stop(self) -> None:
        await self.server.stop()

    async def send(self, msg: OutboundMessage) -> None:
        """Broadcast reply to all connected Gateway clients."""
        await self.server.broadcast({"method": "reply", "params": {"text": msg.text}})
```

**Step 5: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_gateway_server.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add mindclaw/gateway/server.py mindclaw/gateway/channel.py tests/test_gateway_server.py
git commit -m "feat(phase5): add GatewayServer (WebSocket JSON-RPC) and GatewayChannel"
```

---

### Task 8: TelegramChannel

**Files:**
- Create: `mindclaw/channels/telegram.py`
- Test: `tests/test_telegram_channel.py`

Since python-telegram-bot requires a real bot token for integration testing, we test with mocks.

**Step 1: Write the failing tests**

Create `tests/test_telegram_channel.py`:

```python
# input: mindclaw.channels.telegram
# output: TelegramChannel 测试 (mocked)
# pos: Telegram 渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_telegram_channel_init():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_from=["123"])
    assert ch.name == "telegram"
    assert ch.is_allowed("123")
    assert not ch.is_allowed("999")
    assert ch.allow_groups is False


def test_telegram_channel_groups_disabled():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_groups=False)
    assert ch.allow_groups is False


def test_telegram_channel_groups_enabled():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_groups=True)
    assert ch.allow_groups is True


@pytest.mark.asyncio
async def test_telegram_on_message_private():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_from=None)

    # Simulate a Telegram Update
    update = MagicMock()
    update.effective_message.text = "hello from telegram"
    update.effective_user.id = 12345
    update.effective_user.username = "alice"
    update.effective_user.first_name = "Alice"
    update.effective_chat.id = 12345
    update.effective_chat.type = "private"

    context = MagicMock()
    await ch._on_message(update, context)

    msg = await bus.get_inbound()
    assert msg.channel == "telegram"
    assert msg.text == "hello from telegram"
    assert msg.user_id == "12345"
    assert msg.chat_id == "12345"


@pytest.mark.asyncio
async def test_telegram_on_message_group_blocked():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_groups=False)

    update = MagicMock()
    update.effective_message.text = "group msg"
    update.effective_user.id = 12345
    update.effective_chat.id = -100123
    update.effective_chat.type = "group"

    context = MagicMock()
    await ch._on_message(update, context)

    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_telegram_on_message_group_allowed():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_groups=True)

    update = MagicMock()
    update.effective_message.text = "group msg"
    update.effective_user.id = 12345
    update.effective_user.username = "bob"
    update.effective_user.first_name = "Bob"
    update.effective_chat.id = -100123
    update.effective_chat.type = "group"

    context = MagicMock()
    await ch._on_message(update, context)

    msg = await bus.get_inbound()
    assert msg.text == "group msg"


@pytest.mark.asyncio
async def test_telegram_send():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")
    ch._bot = AsyncMock()

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="reply text")
    await ch.send(msg)

    ch._bot.send_message.assert_awaited_once_with(
        chat_id=12345, text="reply text", parse_mode="Markdown",
    )
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_telegram_channel.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement TelegramChannel**

Create `mindclaw/channels/telegram.py`:

```python
# input: channels/base.py, bus/events.py, python-telegram-bot
# output: 导出 TelegramChannel
# pos: Telegram 渠道实现，使用 polling 模式接收消息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class TelegramChannel(BaseChannel):
    """Telegram channel using python-telegram-bot (polling mode)."""

    def __init__(
        self,
        bus: MessageBus,
        token: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="telegram", bus=bus, allow_from=allow_from)
        self._token = token
        self.allow_groups = allow_groups
        self._app = None
        self._bot = None

    async def start(self) -> None:
        self._app = ApplicationBuilder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        await self._app.initialize()
        self._bot = self._app.bot
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, msg: OutboundMessage) -> None:
        if self._bot:
            await self._bot.send_message(
                chat_id=int(msg.chat_id),
                text=msg.text,
                parse_mode="Markdown",
            )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat

        if message is None or user is None or chat is None:
            return

        if not message.text:
            return

        # Group filter
        if chat.type != "private" and not self.allow_groups:
            return

        username = user.username or user.first_name or str(user.id)

        await self._handle_message(
            text=message.text,
            chat_id=str(chat.id),
            user_id=str(user.id),
            username=username,
        )
```

**Step 4: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_telegram_channel.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add mindclaw/channels/telegram.py tests/test_telegram_channel.py
git commit -m "feat(phase5): add TelegramChannel with polling and group filtering"
```

---

### Task 9: MindClawApp Orchestrator

**Files:**
- Create: `mindclaw/app.py`
- Test: `tests/test_app.py`

**Step 1: Write the failing tests**

Create `tests/test_app.py`:

```python
# input: mindclaw.app
# output: MindClawApp 编排器测试
# pos: 顶层编排器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.config.schema import MindClawConfig


def test_app_instantiation():
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)
    assert app.bus is not None
    assert app.channel_manager is not None
    assert app.agent_loop is not None
    assert app.approval_manager is not None


def test_app_register_tools():
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)
    app._register_tools()
    # Should have at least the basic tools
    assert app.tool_registry.get("read_file") is not None
    assert app.tool_registry.get("list_dir") is not None


@pytest.mark.asyncio
async def test_app_outbound_routing():
    """Outbound messages should be dispatched to the right channel."""
    from mindclaw.app import MindClawApp
    from mindclaw.channels.base import BaseChannel

    class FakeChannel(BaseChannel):
        def __init__(self, bus):
            super().__init__(name="fake", bus=bus)
            self.sent = []
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg):
            self.sent.append(msg)

    config = MindClawConfig()
    app = MindClawApp(config)
    fake_ch = FakeChannel(app.bus)
    app.channel_manager.register(fake_ch)

    # Put outbound message
    out = OutboundMessage(channel="fake", chat_id="c1", text="hello")
    await app.bus.put_outbound(out)

    # Run outbound router briefly
    router_task = asyncio.create_task(app._outbound_router())
    await asyncio.sleep(0.1)
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert len(fake_ch.sent) == 1
    assert fake_ch.sent[0].text == "hello"


@pytest.mark.asyncio
async def test_app_message_router_dispatches_to_agent():
    """Normal messages should be dispatched to the agent loop."""
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    handled = []
    original_handle = app.agent_loop.handle_message

    async def mock_handle(msg):
        handled.append(msg)

    app.agent_loop.handle_message = mock_handle

    # Put inbound message
    inbound = InboundMessage(
        channel="cli", chat_id="local",
        user_id="u1", username="alice", text="hi"
    )
    await app.bus.put_inbound(inbound)

    router_task = asyncio.create_task(app._message_router())
    await asyncio.sleep(0.1)
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert len(handled) == 1
    assert handled[0].text == "hi"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_app.py -v -x`
Expected: FAIL — module not found.

**Step 3: Implement MindClawApp**

Create `mindclaw/app.py`:

```python
# input: config/schema.py, bus/queue.py, channels/manager.py, orchestrator/agent_loop.py,
#        security/approval.py, knowledge/session.py, knowledge/memory.py,
#        orchestrator/context.py, llm/router.py, tools/*, gateway/*
# output: 导出 MindClawApp
# pos: 顶层编排器，统一管理所有组件的生命周期和消息路由
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import secrets
from pathlib import Path

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.cli_channel import CLIChannel
from mindclaw.channels.manager import ChannelManager
from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.file_ops import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from mindclaw.tools.registry import ToolRegistry
from mindclaw.tools.shell import ExecTool
from mindclaw.tools.web import WebFetchTool, WebSearchTool


class MindClawApp:
    """Top-level orchestrator that wires all components together."""

    def __init__(self, config: MindClawConfig) -> None:
        self.config = config
        self.bus = MessageBus()
        self.router = LLMRouter(config)
        self.channel_manager = ChannelManager(self.bus)
        self.tool_registry = ToolRegistry()

        data_dir = Path(config.knowledge.data_dir)
        self.session_store = SessionStore(data_dir=data_dir)
        self.memory_manager = MemoryManager(
            data_dir=data_dir, router=self.router, config=config,
        )
        self.context_builder = ContextBuilder(memory_manager=self.memory_manager)

        self.approval_manager = ApprovalManager(
            bus=self.bus, timeout=config.security.approval_timeout,
        )

        self.agent_loop = AgentLoop(
            config=config,
            bus=self.bus,
            router=self.router,
            tool_registry=self.tool_registry,
            approval_manager=self.approval_manager,
            session_store=self.session_store,
            memory_manager=self.memory_manager,
            context_builder=self.context_builder,
        )

        self._gateway_auth = None
        self._agent_task: asyncio.Task | None = None

    def _register_tools(self) -> None:
        workspace = Path.cwd()
        self.tool_registry.register(ReadFileTool(workspace=workspace))
        self.tool_registry.register(WriteFileTool(workspace=workspace))
        self.tool_registry.register(EditFileTool(workspace=workspace))
        self.tool_registry.register(ListDirTool(workspace=workspace))
        self.tool_registry.register(
            ExecTool(workspace=workspace, timeout=self.config.tools.exec_timeout)
        )
        self.tool_registry.register(WebFetchTool())

        brave_settings = self.config.providers.get("brave")
        if brave_settings and brave_settings.api_key:
            self.tool_registry.register(WebSearchTool(api_key=brave_settings.api_key))

    def _setup_channels(self, channel_names: list[str]) -> None:
        for name in channel_names:
            if name == "cli":
                self.channel_manager.register(CLIChannel(bus=self.bus))
            elif name == "gateway":
                self._setup_gateway()
            elif name == "telegram":
                self._setup_telegram()
            else:
                logger.warning(f"Unknown channel: {name}")

    def _setup_gateway(self) -> None:
        from mindclaw.gateway.auth import GatewayAuthManager
        from mindclaw.gateway.channel import GatewayChannel
        from mindclaw.gateway.server import GatewayServer

        data_dir = Path(self.config.knowledge.data_dir)
        token = self.config.gateway.token
        if not token:
            token_path = data_dir / "gateway_token"
            if token_path.exists():
                token = token_path.read_text().strip()
            else:
                token = secrets.token_urlsafe(32)
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(token)
                token_path.chmod(0o600)
                logger.info(f"Generated gateway token: {token}")

        self._gateway_auth = GatewayAuthManager(
            token=token,
            paired_devices_path=data_dir / "paired_devices.json",
        )

        async def on_gateway_message(device_id: str, text: str) -> None:
            await self.bus.put_inbound(
                __import__("mindclaw.bus.events", fromlist=["InboundMessage"]).InboundMessage(
                    channel="gateway",
                    chat_id=device_id,
                    user_id=device_id,
                    username=device_id,
                    text=text,
                )
            )

        server = GatewayServer(
            host=self.config.gateway.host,
            port=self.config.gateway.port,
            auth_manager=self._gateway_auth,
            on_message=on_gateway_message,
        )
        self.channel_manager.register(GatewayChannel(bus=self.bus, server=server))

    def _setup_telegram(self) -> None:
        from mindclaw.channels.telegram import TelegramChannel

        tg_config = self.config.channels.get("telegram")
        if not tg_config or not tg_config.token:
            logger.warning("Telegram channel configured but no token provided, skipping")
            return

        self.channel_manager.register(TelegramChannel(
            bus=self.bus,
            token=tg_config.token,
            allow_from=tg_config.allow_from or None,
            allow_groups=tg_config.allow_groups,
        ))

    async def _process_message(self, msg) -> None:
        try:
            await self.agent_loop.handle_message(msg)
        except Exception:
            logger.exception("Agent error")
            await self.bus.put_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                text="An internal error occurred. Please try again.",
            ))

    async def _message_router(self) -> None:
        while True:
            msg = await self.bus.get_inbound()

            # 1. Pairing reply interception
            if self._gateway_auth and self._gateway_auth.is_pairing_reply(msg.text):
                self._gateway_auth.handle_pairing_reply(msg.text)
                continue

            # 2. Approval reply interception
            if self.approval_manager.has_pending() and \
               self.approval_manager.is_approval_reply(msg.text):
                self.approval_manager.resolve(msg.text)
                continue

            # 3. Drop non-approval messages during pending approval
            if self.approval_manager.has_pending():
                logger.debug(f"Ignoring message during pending approval: {msg.text[:50]}")
                continue

            # 4. Wait for previous agent task
            if self._agent_task is not None and not self._agent_task.done():
                try:
                    await self._agent_task
                except Exception:
                    pass

            self._agent_task = asyncio.create_task(self._process_message(msg))

    async def _outbound_router(self) -> None:
        while True:
            msg = await self.bus.get_outbound()
            await self.channel_manager.dispatch_outbound(msg)

    async def run(self, channel_names: list[str]) -> None:
        # Configure loguru
        logger.remove()
        logger.add(
            self.config.log.file,
            level=self.config.log.level,
            rotation=self.config.log.rotation,
            retention=self.config.log.retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
        )

        self._register_tools()
        self._setup_channels(channel_names)

        tasks = [
            asyncio.create_task(self.channel_manager.start_all()),
            asyncio.create_task(self._message_router()),
            asyncio.create_task(self._outbound_router()),
        ]

        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            if self._agent_task and not self._agent_task.done():
                self._agent_task.cancel()
                try:
                    await self._agent_task
                except asyncio.CancelledError:
                    pass
            await self.channel_manager.stop_all()
```

**Step 4: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_app.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add mindclaw/app.py tests/test_app.py
git commit -m "feat(phase5): add MindClawApp orchestrator with message routing and channel setup"
```

---

### Task 10: CLI Commands Refactor + Secret Commands

**Files:**
- Modify: `mindclaw/cli/commands.py`
- Modify: `mindclaw/config/loader.py`
- Test: `tests/test_commands.py` (new)

**Step 1: Write the failing tests**

Create `tests/test_commands.py`:

```python
# input: mindclaw.cli.commands
# output: CLI 命令测试
# pos: CLI 入口层测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

from typer.testing import CliRunner

runner = CliRunner()


def test_version_command():
    from mindclaw.cli.commands import app

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "MindClaw" in result.output


def test_secret_set_and_list(tmp_path):
    from mindclaw.cli.commands import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"knowledge": {"dataDir": str(data_dir)}}))

    result = runner.invoke(app, ["secret-set", "MY_KEY", "my_value", "-c", str(config_path)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["secret-list", "-c", str(config_path)])
    assert result.exit_code == 0
    assert "MY_KEY" in result.output


def test_secret_delete(tmp_path):
    from mindclaw.cli.commands import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"knowledge": {"dataDir": str(data_dir)}}))

    runner.invoke(app, ["secret-set", "DEL_KEY", "val", "-c", str(config_path)])
    result = runner.invoke(app, ["secret-delete", "DEL_KEY", "-c", str(config_path)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["secret-list", "-c", str(config_path)])
    assert "DEL_KEY" not in result.output
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_commands.py -v -x`
Expected: FAIL — `secret-set` command not found.

**Step 3: Rewrite commands.py**

Replace `mindclaw/cli/commands.py`:

```python
# input: typer, app.py, config/loader.py, security/crypto.py
# output: 导出 app (Typer 应用)
# pos: CLI 入口，chat/serve/secret 命令
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from mindclaw.config.loader import load_config

app = typer.Typer(name="mindclaw", help="MindClaw - Personal AI Assistant")
console = Console()


@app.command()
def chat(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start an interactive CLI chat session."""
    from mindclaw.app import MindClawApp

    cfg = load_config(config)
    mindclaw_app = MindClawApp(cfg)
    asyncio.run(mindclaw_app.run(["cli"]))


@app.command()
def serve(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start Gateway + remote channels (Telegram, etc.)."""
    from mindclaw.app import MindClawApp

    cfg = load_config(config)
    mindclaw_app = MindClawApp(cfg)
    asyncio.run(mindclaw_app.run(["gateway", "telegram"]))


@app.command("secret-set")
def secret_set(
    name: str = typer.Argument(help="Secret name"),
    value: str = typer.Argument(help="Secret value"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Store an encrypted secret."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    store.set(name, value)
    console.print(f"Secret '{name}' stored.")


@app.command("secret-list")
def secret_list(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """List all stored secret names."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    keys = store.list_keys()
    if not keys:
        console.print("No secrets stored.")
    else:
        for k in keys:
            console.print(f"  {k}")


@app.command("secret-delete")
def secret_delete(
    name: str = typer.Argument(help="Secret name to delete"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Delete a stored secret."""
    from mindclaw.security.crypto import SecretStore

    cfg = load_config(config)
    data_dir = Path(cfg.knowledge.data_dir)
    store = SecretStore(
        store_path=data_dir / "secrets.enc",
        master_key_path=data_dir / "master.key",
    )
    store.init_or_load_key()
    store.delete(name)
    console.print(f"Secret '{name}' deleted.")


@app.command()
def version() -> None:
    """Show MindClaw version."""
    from mindclaw import __version__

    console.print(f"MindClaw v{__version__}")


if __name__ == "__main__":
    app()
```

**Step 4: Run tests**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest tests/test_commands.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add mindclaw/cli/commands.py tests/test_commands.py
git commit -m "feat(phase5): refactor CLI to chat/serve/secret commands via MindClawApp"
```

---

### Task 11: Update Documentation + _ARCHITECTURE.md

**Files:**
- Modify: `mindclaw/_ARCHITECTURE.md`
- Modify: `mindclaw/channels/_ARCHITECTURE.md`
- Modify: `mindclaw/gateway/_ARCHITECTURE.md`
- Modify: `mindclaw/security/_ARCHITECTURE.md`
- Modify: `mindclaw/cli/_ARCHITECTURE.md`
- Modify: `mindclaw/config/_ARCHITECTURE.md`
- Modify: `CLAUDE.md` (update Phase progress)
- Modify: `config.example.json`

**Step 1: Update all _ARCHITECTURE.md files**

Each file should reflect the new/modified files in its folder. See the design doc section 8 for the full file list.

Key updates:
- `mindclaw/_ARCHITECTURE.md`: Add `app.py`
- `mindclaw/channels/_ARCHITECTURE.md`: Add `manager.py`, `telegram.py`
- `mindclaw/gateway/_ARCHITECTURE.md`: Add `server.py`, `auth.py`, `channel.py`
- `mindclaw/security/_ARCHITECTURE.md`: Add `crypto.py`
- `mindclaw/cli/_ARCHITECTURE.md`: Update `commands.py` description
- `mindclaw/config/_ARCHITECTURE.md`: Update `schema.py` description

**Step 2: Update config.example.json**

Add `channels` section with telegram example:

```json
{
  "agent": { "defaultModel": "claude-sonnet-4-20250514" },
  "gateway": { "host": "127.0.0.1", "port": 8765 },
  "channels": {
    "telegram": {
      "token": "$TELEGRAM_BOT_TOKEN",
      "allowFrom": [],
      "allowGroups": false
    }
  },
  "providers": {
    "anthropic": { "apiKey": "$ANTHROPIC_API_KEY" }
  },
  "tools": { "execTimeout": 30 },
  "knowledge": { "dataDir": "data" }
}
```

**Step 3: Update CLAUDE.md phase progress**

Change `当前进度：Phase 5 (Gateway + Telegram) — Phase 0-4 已完成` to reflect Phase 5 completion.

**Step 4: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "docs(phase5): update all _ARCHITECTURE.md files, config.example.json, and CLAUDE.md"
```

---

### Task 12: Final Integration Verification

**Step 1: Run ruff linter**

Run: `cd /Users/wzb/Documents/mindclaw && uv run ruff check mindclaw/ tests/`
Expected: No errors (fix any that appear)

**Step 2: Run full test suite**

Run: `cd /Users/wzb/Documents/mindclaw && uv run pytest -v --tb=short`
Expected: ALL PASS

**Step 3: Verify CLI commands work**

Run: `cd /Users/wzb/Documents/mindclaw && uv run mindclaw version`
Expected: Shows version

Run: `cd /Users/wzb/Documents/mindclaw && uv run mindclaw --help`
Expected: Shows chat, serve, secret-set, secret-list, secret-delete, version

**Step 4: Verify secret store works end-to-end**

```bash
cd /Users/wzb/Documents/mindclaw
uv run mindclaw secret-set TEST_KEY test_value
uv run mindclaw secret-list
uv run mindclaw secret-delete TEST_KEY
```

**Step 5: Final commit (if any fixes)**

```bash
git add -A
git commit -m "fix(phase5): address linting and integration issues"
```
