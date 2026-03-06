# MindClaw Phase 0-2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 从零搭建 MindClaw 项目，完成环境搭建 + CLI 对话 + 工具系统三个阶段，实现一个能通过终端对话、调用工具的 AI 助手。

**Architecture:** 6 层架构的底层 3 层——配置层 (Pydantic) → 大脑层 (LiteLLM) → 消息总线 (asyncio.Queue) → 编排层 (ReAct Agent Loop) → CLI 渠道 (prompt-toolkit) → 工具层 (Tool 抽象 + Registry)。Phase 0-2 暂不涉及安全审批、Gateway、子 Agent、插件系统。

**Tech Stack:** Python 3.12+ / uv / asyncio / LiteLLM / Pydantic v2 / Typer + Rich / prompt-toolkit / httpx / loguru / pytest + pytest-asyncio

**PRD 参考:** `docs/plans/2026-03-06-mindclaw-prd.md`

---

## Phase 0: 环境搭建

> 里程碑: `python -c "import mindclaw"` 成功运行

### Task 0.1: 安装 Python 3.12 和 uv

**当前环境:** macOS, Homebrew 已安装, 仅有系统 Python 3.9.6, 无 uv

**Step 1: 安装 Python 3.12**

```bash
brew install python@3.12
```

验证: `python3.12 --version` 输出 `Python 3.12.x`

**Step 2: 安装 uv**

```bash
brew install uv
```

验证: `uv --version` 输出版本号

**Step 3: 确认工具链就绪**

```bash
python3.12 --version && uv --version && git --version
```

Expected: 三个版本号均正常输出

---

### Task 0.2: 初始化 Git 仓库

**Step 1: 初始化 git**

```bash
cd /Users/wzb/Documents/mindclaw
git init
```

**Step 2: 创建 .gitignore**

创建文件: `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.eggs/

# Virtual env
.venv/

# IDE
.idea/
.vscode/
*.swp

# Config (含敏感信息)
config.json

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Session data
sessions/

# Knowledge data
data/
```

**Step 3: 首次提交**

```bash
git add .gitignore CLAUDE.md docs/
git commit -m "init: project skeleton with PRD and CLAUDE.md"
```

---

### Task 0.3: 创建项目骨架 (pyproject.toml + 包结构)

**Files:**
- Create: `pyproject.toml`
- Create: `mindclaw/__init__.py`
- Create: `mindclaw/cli/__init__.py`
- Create: `mindclaw/gateway/__init__.py`
- Create: `mindclaw/channels/__init__.py`
- Create: `mindclaw/bus/__init__.py`
- Create: `mindclaw/orchestrator/__init__.py`
- Create: `mindclaw/llm/__init__.py`
- Create: `mindclaw/security/__init__.py`
- Create: `mindclaw/tools/__init__.py`
- Create: `mindclaw/plugins/__init__.py`
- Create: `mindclaw/knowledge/__init__.py`
- Create: `mindclaw/config/__init__.py`
- Create: `tests/__init__.py`

**Step 1: 创建 pyproject.toml**

```toml
[project]
name = "mindclaw"
version = "0.1.0"
description = "Personal AI assistant framework - secure, extensible, multi-channel, multi-model"
requires-python = ">=3.12"
dependencies = [
    "litellm>=1.55",
    "pydantic>=2.0",
    "typer>=0.15",
    "rich>=13.0",
    "prompt-toolkit>=3.0",
    "httpx>=0.28",
    "loguru>=0.7",
    "websockets>=14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "ruff>=0.9",
]

[project.scripts]
mindclaw = "mindclaw.cli.commands:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: 创建包结构**

```bash
mkdir -p mindclaw/{cli,gateway,channels,bus,orchestrator,llm,security,tools,plugins,knowledge,config,skills,templates}
mkdir -p tests
mkdir -p plugins
```

每个 `__init__.py` 暂时为空文件，除了主包:

`mindclaw/__init__.py`:
```python
# input: 无
# output: 导出 __version__
# pos: 包入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md
"""MindClaw - Personal AI Assistant Framework."""

__version__ = "0.1.0"
```

**Step 3: 安装项目 (editable mode)**

```bash
cd /Users/wzb/Documents/mindclaw
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Step 4: 验证里程碑**

```bash
python -c "import mindclaw; print(mindclaw.__version__)"
```

Expected: `0.1.0`

**Step 5: 验证 ruff**

```bash
ruff check mindclaw/
```

Expected: 无错误

**Step 6: 创建文件夹级 _ARCHITECTURE.md**

为 `mindclaw/` 目录创建 `_ARCHITECTURE.md`:

```markdown
> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

MindClaw 主包入口，包含 6 层架构的所有子模块。

| 文件/目录 | 地位 | 功能 |
|-----------|------|------|
| `__init__.py` | 包入口 | 导出 __version__ |
| `cli/` | 用户接口层 | CLI 命令定义 (Typer) |
| `gateway/` | 网关层 | WebSocket Gateway |
| `channels/` | 渠道层 | 各平台渠道适配 |
| `bus/` | 消息总线层 | 异步消息路由 |
| `orchestrator/` | 编排层 | Agent Loop + 子 Agent |
| `llm/` | 大脑层 | LLM 路由 + 缓存 |
| `security/` | 安全层 | 认证 + 审批 + 沙箱 |
| `tools/` | 工具层 | 工具抽象 + 内置工具 |
| `plugins/` | 插件系统 | 插件加载 + Hook |
| `knowledge/` | 知识层 | 记忆 + 知识源 |
| `config/` | 配置层 | Pydantic 配置 |
| `skills/` | 技能 | Markdown 技能文件 |
| `templates/` | 模板 | SOUL.md / AGENTS.md |
```

**Step 7: 提交**

```bash
git add -A
git commit -m "feat(phase0): project skeleton with pyproject.toml and package structure"
```

---

### Task 0.4: 配置 pytest 基础

**Files:**
- Create: `tests/test_import.py`

**Step 1: 写冒烟测试**

`tests/test_import.py`:
```python
# input: mindclaw 包
# output: 冒烟测试
# pos: 基础导入验证
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

def test_import():
    import mindclaw
    assert mindclaw.__version__ == "0.1.0"
```

**Step 2: 运行测试**

```bash
pytest tests/test_import.py -v
```

Expected: `PASSED`

**Step 3: 提交**

```bash
git add tests/
git commit -m "test(phase0): add smoke test for package import"
```

---

## Phase 1: CLI 对话 + 单模型

> 里程碑: 终端输入问题 -> Claude 回复答案

### Task 1.1: 配置系统 (Pydantic Schema + Loader)

**Files:**
- Create: `mindclaw/config/schema.py`
- Create: `mindclaw/config/loader.py`
- Create: `config.example.json`
- Test: `tests/test_config.py`

**Step 1: 写 config 失败测试**

`tests/test_config.py`:
```python
# input: mindclaw.config
# output: 配置系统测试
# pos: 配置层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from pathlib import Path


def test_config_schema_defaults():
    """默认配置应该有合理的默认值"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig()
    assert config.agent.default_model == "claude-sonnet-4-20250514"
    assert config.agent.max_iterations == 40
    assert config.agent.subagent_max_iterations == 15


def test_config_schema_custom_values():
    """应该能覆盖默认值"""
    from mindclaw.config.schema import MindClawConfig

    config = MindClawConfig(agent={"default_model": "gpt-4o", "max_iterations": 20})
    assert config.agent.default_model == "gpt-4o"
    assert config.agent.max_iterations == 20


def test_config_env_var_resolution(monkeypatch):
    """配置中的 $ENV_VAR 应被环境变量替换"""
    from mindclaw.config.loader import resolve_env_vars

    monkeypatch.setenv("TEST_API_KEY", "sk-test-123")
    result = resolve_env_vars({"apiKey": "$TEST_API_KEY"})
    assert result["apiKey"] == "sk-test-123"


def test_config_env_var_missing():
    """缺失的环境变量应保留原值并给出警告"""
    from mindclaw.config.loader import resolve_env_vars

    result = resolve_env_vars({"apiKey": "$NONEXISTENT_VAR"})
    assert result["apiKey"] == "$NONEXISTENT_VAR"


def test_config_load_from_file(tmp_path):
    """应该能从 JSON 文件加载配置"""
    import json
    from mindclaw.config.loader import load_config

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "agent": {"defaultModel": "gpt-4o"}
    }))

    config = load_config(config_file)
    assert config.agent.default_model == "gpt-4o"


def test_config_load_default_when_no_file():
    """无配置文件时应返回默认配置"""
    from mindclaw.config.loader import load_config

    config = load_config(Path("/nonexistent/config.json"))
    assert config.agent.default_model == "claude-sonnet-4-20250514"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL (模块不存在)

**Step 3: 实现 config/schema.py**

`mindclaw/config/schema.py`:
```python
# input: pydantic
# output: 导出 MindClawConfig, AgentConfig, GatewayConfig, ProviderConfig 等
# pos: 配置层核心，定义所有配置的 Pydantic 模型
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    default_model: str = Field(default="claude-sonnet-4-20250514", alias="defaultModel")
    fallback_model: str = Field(default="gpt-4o", alias="fallbackModel")
    max_iterations: int = Field(default=40, alias="maxIterations")
    subagent_max_iterations: int = Field(default=15, alias="subagentMaxIterations")

    model_config = {"populate_by_name": True}


class GatewayConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765

    model_config = {"populate_by_name": True}


class ProviderSettings(BaseModel):
    api_key: str = Field(default="", alias="apiKey")
    api_base: str | None = Field(default=None, alias="apiBase")

    model_config = {"populate_by_name": True}


class ToolsConfig(BaseModel):
    exec_timeout: int = Field(default=30, alias="execTimeout")
    tool_result_max_chars: int = Field(default=500, alias="toolResultMaxChars")
    restrict_to_workspace: bool = Field(default=True, alias="restrictToWorkspace")

    model_config = {"populate_by_name": True}


class LogConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/mindclaw.log"
    rotation: str = "10 MB"
    retention: str = "7 days"

    model_config = {"populate_by_name": True}


class MindClawConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    model_config = {"populate_by_name": True}
```

**Step 4: 实现 config/loader.py**

`mindclaw/config/loader.py`:
```python
# input: config/schema.py, json, os, pathlib
# output: 导出 load_config(), resolve_env_vars()
# pos: 配置加载器，从 JSON 文件加载并解析环境变量
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import os
from pathlib import Path

from loguru import logger

from .schema import MindClawConfig


def resolve_env_vars(data: dict | list | str) -> dict | list | str:
    """递归解析配置中的 $ENV_VAR 引用"""
    if isinstance(data, str):
        if data.startswith("$") and not data.startswith("$$"):
            env_name = data[1:]
            value = os.environ.get(env_name)
            if value is None:
                logger.warning(f"Environment variable {env_name} not set, keeping raw value")
                return data
            return value
        return data
    if isinstance(data, dict):
        return {k: resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [resolve_env_vars(item) for item in data]
    return data


def load_config(path: Path | None = None) -> MindClawConfig:
    """从 JSON 文件加载配置，文件不存在则返回默认配置"""
    if path is None:
        path = Path("config.json")

    if not path.exists():
        logger.info(f"Config file {path} not found, using defaults")
        return MindClawConfig()

    raw = json.loads(path.read_text())
    resolved = resolve_env_vars(raw)
    return MindClawConfig(**resolved)
```

**Step 5: 创建 config.example.json**

`config.example.json`:
```json
{
  "agent": {
    "defaultModel": "claude-sonnet-4-20250514",
    "fallbackModel": "gpt-4o",
    "maxIterations": 40
  },
  "providers": {
    "anthropic": { "apiKey": "$ANTHROPIC_API_KEY" },
    "openai": { "apiKey": "$OPENAI_API_KEY" }
  },
  "log": {
    "level": "INFO"
  }
}
```

**Step 6: 运行测试**

```bash
pytest tests/test_config.py -v
```

Expected: 全部 PASSED

**Step 7: 创建 config/ _ARCHITECTURE.md 并提交**

```bash
git add mindclaw/config/ config.example.json tests/test_config.py
git commit -m "feat(phase1): config system with Pydantic schema and env var resolution"
```

---

### Task 1.2: LLM 路由层 (LiteLLM 封装)

**Files:**
- Create: `mindclaw/llm/router.py`
- Test: `tests/test_llm.py`

**Step 1: 写失败测试**

`tests/test_llm.py`:
```python
# input: mindclaw.llm
# output: LLM 路由层测试
# pos: 大脑层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_llm_router_chat_returns_text():
    """chat() 应返回 LLM 的文本回复"""
    from mindclaw.llm.router import LLMRouter
    from mindclaw.config.schema import MindClawConfig

    router = LLMRouter(MindClawConfig())

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.choices[0].message.tool_calls = None

    with patch("mindclaw.llm.router.acompletion", return_value=mock_response):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Hello!"
    assert result.tool_calls is None


@pytest.mark.asyncio
async def test_llm_router_chat_with_tool_calls():
    """chat() 应正确返回工具调用"""
    from mindclaw.llm.router import LLMRouter
    from mindclaw.config.schema import MindClawConfig

    router = LLMRouter(MindClawConfig())

    mock_tool_call = AsyncMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = '{"path": "/tmp/test.txt"}'

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = None
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    with patch("mindclaw.llm.router.acompletion", return_value=mock_response):
        result = await router.chat(
            messages=[{"role": "user", "content": "read /tmp/test.txt"}],
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )

    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function.name == "read_file"


def test_llm_router_model_resolution():
    """应正确解析模型名称"""
    from mindclaw.llm.router import LLMRouter
    from mindclaw.config.schema import MindClawConfig

    router = LLMRouter(MindClawConfig())
    assert router.resolve_model(None) == "claude-sonnet-4-20250514"
    assert router.resolve_model("gpt-4o") == "gpt-4o"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_llm.py -v
```

Expected: FAIL

**Step 3: 实现 llm/router.py**

`mindclaw/llm/router.py`:
```python
# input: litellm, config/schema.py
# output: 导出 LLMRouter, ChatResult
# pos: 大脑层核心，统一 LLM 调用接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from dataclasses import dataclass, field
from typing import Any

from litellm import acompletion
from loguru import logger

from mindclaw.config.schema import MindClawConfig


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[Any] | None


class LLMRouter:
    def __init__(self, config: MindClawConfig):
        self.config = config

    def resolve_model(self, model: str | None) -> str:
        return model or self.config.agent.default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        resolved_model = self.resolve_model(model)
        logger.debug(f"LLM call: model={resolved_model}, messages={len(messages)}")

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await acompletion(**kwargs)
        message = response.choices[0].message

        return ChatResult(
            content=message.content,
            tool_calls=message.tool_calls,
        )
```

**Step 4: 运行测试**

```bash
pytest tests/test_llm.py -v
```

Expected: 全部 PASSED

**Step 5: 提交**

```bash
git add mindclaw/llm/ tests/test_llm.py
git commit -m "feat(phase1): LLM router with LiteLLM integration"
```

---

### Task 1.3: 消息总线 (Message Bus)

**Files:**
- Create: `mindclaw/bus/events.py`
- Create: `mindclaw/bus/queue.py`
- Test: `tests/test_bus.py`

**Step 1: 写失败测试**

`tests/test_bus.py`:
```python
# input: mindclaw.bus
# output: 消息总线测试
# pos: 消息总线层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
import asyncio


def test_inbound_message_session_key():
    """session_key 应为 channel:chat_id"""
    from mindclaw.bus.events import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        chat_id="12345",
        user_id="u1",
        username="alice",
        text="hello",
    )
    assert msg.session_key == "telegram:12345"


def test_outbound_message_has_id():
    """OutboundMessage 应自动生成 message_id"""
    from mindclaw.bus.events import OutboundMessage

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="hi")
    assert msg.message_id  # 非空
    assert len(msg.message_id) > 0


@pytest.mark.asyncio
async def test_message_bus_roundtrip():
    """消息应能通过总线往返传递"""
    from mindclaw.bus.events import InboundMessage, OutboundMessage
    from mindclaw.bus.queue import MessageBus

    bus = MessageBus()

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="hi"
    )
    await bus.put_inbound(inbound)
    got = await bus.get_inbound()
    assert got.text == "hi"

    outbound = OutboundMessage(channel="cli", chat_id="local", text="hello!")
    await bus.put_outbound(outbound)
    got = await bus.get_outbound()
    assert got.text == "hello!"


@pytest.mark.asyncio
async def test_message_bus_get_blocks():
    """get_inbound 应阻塞直到有消息"""
    from mindclaw.bus.events import InboundMessage
    from mindclaw.bus.queue import MessageBus

    bus = MessageBus()

    async def delayed_put():
        await asyncio.sleep(0.05)
        await bus.put_inbound(
            InboundMessage(
                channel="cli", chat_id="local", user_id="wzb", username="wzb", text="delayed"
            )
        )

    asyncio.create_task(delayed_put())
    msg = await bus.get_inbound()
    assert msg.text == "delayed"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_bus.py -v
```

**Step 3: 实现 bus/events.py**

`mindclaw/bus/events.py`:
```python
# input: dataclasses, uuid, time
# output: 导出 InboundMessage, OutboundMessage
# pos: 消息数据类定义，总线层的数据契约
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    channel: str
    chat_id: str
    user_id: str
    username: str
    text: str
    reply_to: str | None = None
    attachments: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def session_key(self) -> str:
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    text: str
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    reply_to: str | None = None
    attachments: list = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
```

**Step 4: 实现 bus/queue.py**

`mindclaw/bus/queue.py`:
```python
# input: asyncio, bus/events.py
# output: 导出 MessageBus
# pos: 消息总线核心，解耦渠道与 Agent
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from .events import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def put_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def get_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def put_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def get_outbound(self) -> OutboundMessage:
        return await self.outbound.get()
```

**Step 5: 运行测试**

```bash
pytest tests/test_bus.py -v
```

Expected: 全部 PASSED

**Step 6: 提交**

```bash
git add mindclaw/bus/ tests/test_bus.py
git commit -m "feat(phase1): message bus with inbound/outbound queues"
```

---

### Task 1.4: 最简 Agent Loop (纯对话，无工具)

**Files:**
- Create: `mindclaw/orchestrator/agent_loop.py`
- Test: `tests/test_agent_loop.py`

**Step 1: 写失败测试**

`tests/test_agent_loop.py`:
```python
# input: mindclaw.orchestrator
# output: Agent Loop 测试
# pos: 编排层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from unittest.mock import AsyncMock, patch

from mindclaw.bus.events import InboundMessage
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult


@pytest.mark.asyncio
async def test_agent_loop_simple_reply():
    """Agent 应处理一条消息并返回 LLM 回复"""
    from mindclaw.orchestrator.agent_loop import AgentLoop
    from mindclaw.llm.router import LLMRouter
    from mindclaw.bus.queue import MessageBus

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="What is Python?"
    )

    mock_result = ChatResult(content="Python is a programming language.", tool_calls=None)

    with patch.object(router, "chat", return_value=mock_result) as mock_chat:
        await agent.handle_message(inbound)

    # 验证回复被放入 outbound 队列
    outbound = await bus.get_outbound()
    assert outbound.text == "Python is a programming language."
    assert outbound.channel == "cli"
    assert outbound.chat_id == "local"


@pytest.mark.asyncio
async def test_agent_loop_builds_system_prompt():
    """Agent 应构建包含系统提示的消息列表"""
    from mindclaw.orchestrator.agent_loop import AgentLoop
    from mindclaw.llm.router import LLMRouter
    from mindclaw.bus.queue import MessageBus

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="hi"
    )

    mock_result = ChatResult(content="hello", tool_calls=None)
    captured_messages = []

    async def capture_chat(messages, **kwargs):
        captured_messages.extend(messages)
        return mock_result

    with patch.object(router, "chat", side_effect=capture_chat):
        await agent.handle_message(inbound)

    # 第一条应该是 system message
    assert captured_messages[0]["role"] == "system"
    # 最后一条应该是 user message
    assert captured_messages[-1]["role"] == "user"
    assert captured_messages[-1]["content"] == "hi"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_agent_loop.py -v
```

**Step 3: 实现 orchestrator/agent_loop.py**

`mindclaw/orchestrator/agent_loop.py`:
```python
# input: bus/queue.py, bus/events.py, llm/router.py, config/schema.py
# output: 导出 AgentLoop
# pos: 编排层核心，ReAct 推理循环
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import LLMRouter

SYSTEM_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message.
"""


class AgentLoop:
    def __init__(
        self,
        config: MindClawConfig,
        bus: MessageBus,
        router: LLMRouter,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        # session_key -> message history
        self._sessions: dict[str, list[dict]] = {}

    def _get_history(self, session_key: str) -> list[dict]:
        if session_key not in self._sessions:
            self._sessions[session_key] = []
        return self._sessions[session_key]

    def _build_messages(self, history: list[dict], user_text: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key
        history = self._get_history(session_key)

        messages = self._build_messages(history, inbound.text)
        logger.info(f"Agent processing: session={session_key}, user={inbound.username}")

        result = await self.router.chat(messages=messages)

        reply_text = result.content or "(no response)"

        # 保存到 session 历史
        history.append({"role": "user", "content": inbound.text})
        history.append({"role": "assistant", "content": reply_text})

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            text=reply_text,
        )
        await self.bus.put_outbound(outbound)

        logger.info(f"Agent replied: session={session_key}, len={len(reply_text)}")
```

**Step 4: 运行测试**

```bash
pytest tests/test_agent_loop.py -v
```

Expected: 全部 PASSED

**Step 5: 提交**

```bash
git add mindclaw/orchestrator/ tests/test_agent_loop.py
git commit -m "feat(phase1): minimal agent loop with ReAct pattern (no tools yet)"
```

---

### Task 1.5: CLI Channel + Typer 命令

**Files:**
- Create: `mindclaw/channels/base.py`
- Create: `mindclaw/channels/cli_channel.py`
- Create: `mindclaw/cli/commands.py`
- Test: `tests/test_cli_channel.py`

**Step 1: 写失败测试**

`tests/test_cli_channel.py`:
```python
# input: mindclaw.channels
# output: CLI Channel 测试
# pos: 渠道层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from unittest.mock import AsyncMock, patch

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_base_channel_is_abstract():
    """BaseChannel 应该是抽象类，不能直接实例化"""
    from mindclaw.channels.base import BaseChannel

    with pytest.raises(TypeError):
        BaseChannel()


@pytest.mark.asyncio
async def test_cli_channel_creates_inbound_message():
    """CLIChannel 应将用户输入转为 InboundMessage 并放入总线"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)

    await channel._handle_input("hello world")

    msg = await bus.get_inbound()
    assert msg.channel == "cli"
    assert msg.chat_id == "local"
    assert msg.text == "hello world"


@pytest.mark.asyncio
async def test_cli_channel_sends_outbound():
    """CLIChannel 应从 outbound 队列读取并输出"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)

    outbound = OutboundMessage(channel="cli", chat_id="local", text="reply text")
    await bus.put_outbound(outbound)

    # _consume_outbound 应该能获取消息
    msg = await bus.get_outbound()
    assert msg.text == "reply text"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_cli_channel.py -v
```

**Step 3: 实现 channels/base.py**

`mindclaw/channels/base.py`:
```python
# input: abc, bus/events.py
# output: 导出 BaseChannel
# pos: 渠道层抽象基类，所有渠道的统一接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod

from mindclaw.bus.queue import MessageBus


class BaseChannel(ABC):
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    @abstractmethod
    async def start(self) -> None:
        """启动渠道"""

    @abstractmethod
    async def stop(self) -> None:
        """停止渠道"""
```

**Step 4: 实现 channels/cli_channel.py**

`mindclaw/channels/cli_channel.py`:
```python
# input: channels/base.py, bus/events.py, prompt_toolkit
# output: 导出 CLIChannel
# pos: CLI 渠道实现，本地终端交互
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import os

from loguru import logger
from rich.console import Console
from rich.markdown import Markdown

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel

console = Console()


class CLIChannel(BaseChannel):
    def __init__(self, bus: MessageBus) -> None:
        super().__init__(bus)
        self._running = False

    async def _handle_input(self, text: str) -> None:
        msg = InboundMessage(
            channel="cli",
            chat_id="local",
            user_id=os.getenv("USER", "user"),
            username=os.getenv("USER", "user"),
            text=text,
        )
        await self.bus.put_inbound(msg)

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
                        break
                    await self._handle_input(text)
                except (EOFError, KeyboardInterrupt):
                    self._running = False
                    break

    async def _output_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.get_outbound(), timeout=0.5)
                console.print()
                console.print(Markdown(msg.text))
                console.print()
            except asyncio.TimeoutError:
                continue

    async def start(self) -> None:
        self._running = True
        console.print("[bold green]MindClaw[/] ready. Type 'exit' to quit.\n")
        await asyncio.gather(self._input_loop(), self._output_loop())

    async def stop(self) -> None:
        self._running = False
```

**Step 5: 实现 cli/commands.py**

`mindclaw/cli/commands.py`:
```python
# input: typer, channels/cli_channel.py, orchestrator/agent_loop.py, llm/router.py, config/loader.py
# output: 导出 app (Typer 应用)
# pos: CLI 入口，用户通过 typer 命令启动 MindClaw
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from mindclaw.bus.queue import MessageBus
from mindclaw.channels.cli_channel import CLIChannel
from mindclaw.config.loader import load_config
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop

app = typer.Typer(name="mindclaw", help="MindClaw - Personal AI Assistant")
console = Console()


async def _run_chat(config_path: Path | None) -> None:
    config = load_config(config_path)

    # 配置 loguru
    logger.remove()
    logger.add(
        config.log.file,
        level=config.log.level,
        rotation=config.log.rotation,
        retention=config.log.retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}",
    )

    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)

    channel = CLIChannel(bus=bus)

    async def agent_consumer():
        while True:
            msg = await bus.get_inbound()
            try:
                await agent.handle_message(msg)
            except Exception as e:
                logger.error(f"Agent error: {e}")
                from mindclaw.bus.events import OutboundMessage
                await bus.put_outbound(
                    OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, text=f"Error: {e}")
                )

    agent_task = asyncio.create_task(agent_consumer())

    try:
        await channel.start()
    finally:
        agent_task.cancel()
        await channel.stop()


@app.command()
def chat(
    config: Path = typer.Option(None, "--config", "-c", help="Path to config.json"),
) -> None:
    """Start an interactive chat session."""
    asyncio.run(_run_chat(config))


@app.command()
def version() -> None:
    """Show MindClaw version."""
    from mindclaw import __version__

    console.print(f"MindClaw v{__version__}")


if __name__ == "__main__":
    app()
```

**Step 6: 运行测试**

```bash
pytest tests/test_cli_channel.py -v
```

Expected: 全部 PASSED

**Step 7: 手动集成测试**

```bash
# 需要设置 ANTHROPIC_API_KEY 环境变量
export ANTHROPIC_API_KEY="your-key-here"
mindclaw chat
# 输入 "hello"，应该收到 Claude 的回复
# 输入 "exit" 退出
```

**Step 8: 提交**

```bash
git add mindclaw/channels/ mindclaw/cli/ tests/test_cli_channel.py
git commit -m "feat(phase1): CLI channel + typer commands - terminal chat works"
```

---

### Task 1.6: loguru 日志配置

**Files:**
- Modify: `mindclaw/cli/commands.py` (已在 Task 1.5 中完成)
- 验证日志输出

**Step 1: 确保 logs 目录在 .gitignore 中** (已在 Task 0.2 完成)

**Step 2: 运行 chat 命令后检查日志**

```bash
mindclaw chat
# 发一条消息后退出
cat logs/mindclaw.log
```

Expected: 看到结构化日志输出

**Step 3: 提交 (如有变更)**

Phase 1 里程碑验证完成后统一提交。

---

### Task 1.7: Phase 1 里程碑验证

**Step 1: 运行全部测试**

```bash
pytest tests/ -v
```

Expected: 全部 PASSED

**Step 2: Ruff 检查**

```bash
ruff check mindclaw/ tests/
```

Expected: 无错误

**Step 3: 端到端验证**

```bash
export ANTHROPIC_API_KEY="your-key"
mindclaw version
mindclaw chat
# 输入: "用 Python 写一个 hello world"
# 应收到合理的代码回复
# 输入: "exit"
```

**Step 4: 创建 _ARCHITECTURE.md 文件**

为 Phase 1 涉及的每个文件夹创建/更新 `_ARCHITECTURE.md`。

**Step 5: 提交里程碑**

```bash
git add -A
git commit -m "milestone(phase1): CLI chat with Claude working end-to-end"
```

---

## Phase 2: 工具系统

> 里程碑: AI 能帮你读文件、搜网页、执行命令

### Task 2.1: 工具抽象基类 + Registry

**Files:**
- Create: `mindclaw/tools/base.py`
- Create: `mindclaw/tools/registry.py`
- Test: `tests/test_tools_base.py`

**Step 1: 写失败测试**

`tests/test_tools_base.py`:
```python
# input: mindclaw.tools
# output: 工具基类和注册表测试
# pos: 工具层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


def test_tool_base_is_abstract():
    """Tool 基类不能直接实例化"""
    from mindclaw.tools.base import Tool

    with pytest.raises(TypeError):
        Tool()


def test_tool_subclass_requires_fields():
    """Tool 子类必须实现所有抽象方法"""
    from mindclaw.tools.base import Tool, RiskLevel

    class MyTool(Tool):
        name = "my_tool"
        description = "A test tool"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE

        async def execute(self, params: dict) -> str:
            return "ok"

    tool = MyTool()
    assert tool.name == "my_tool"
    assert tool.risk_level == RiskLevel.SAFE


def test_registry_register_and_get():
    """应能注册工具并按名称获取"""
    from mindclaw.tools.base import Tool, RiskLevel
    from mindclaw.tools.registry import ToolRegistry

    class FakeTool(Tool):
        name = "fake"
        description = "fake tool"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE

        async def execute(self, params: dict) -> str:
            return "fake result"

    registry = ToolRegistry()
    registry.register(FakeTool())

    assert registry.get("fake") is not None
    assert registry.get("nonexistent") is None


def test_registry_get_all_tools():
    """应返回所有注册工具"""
    from mindclaw.tools.base import Tool, RiskLevel
    from mindclaw.tools.registry import ToolRegistry

    class ToolA(Tool):
        name = "tool_a"
        description = "A"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE
        async def execute(self, params): return "a"

    class ToolB(Tool):
        name = "tool_b"
        description = "B"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.MODERATE
        async def execute(self, params): return "b"

    registry = ToolRegistry()
    registry.register(ToolA())
    registry.register(ToolB())

    tools = registry.all()
    assert len(tools) == 2


def test_registry_to_openai_schema():
    """应能生成 OpenAI function calling 格式的 schema"""
    from mindclaw.tools.base import Tool, RiskLevel
    from mindclaw.tools.registry import ToolRegistry

    class ReadFile(Tool):
        name = "read_file"
        description = "Read a file"
        parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"],
        }
        risk_level = RiskLevel.SAFE
        async def execute(self, params): return "content"

    registry = ToolRegistry()
    registry.register(ReadFile())

    schemas = registry.to_openai_tools()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "read_file"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_tools_base.py -v
```

**Step 3: 实现 tools/base.py**

`mindclaw/tools/base.py`:
```python
# input: abc, enum
# output: 导出 Tool, RiskLevel
# pos: 工具层抽象基类，所有工具的统一接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod
from enum import Enum


class RiskLevel(Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class Tool(ABC):
    name: str
    description: str
    parameters: dict
    risk_level: RiskLevel

    @abstractmethod
    async def execute(self, params: dict) -> str:
        """执行工具并返回结果字符串"""
```

**Step 4: 实现 tools/registry.py**

`mindclaw/tools/registry.py`:
```python
# input: tools/base.py
# output: 导出 ToolRegistry
# pos: 工具注册表，管理所有可用工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from .base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]
```

**Step 5: 运行测试**

```bash
pytest tests/test_tools_base.py -v
```

Expected: 全部 PASSED

**Step 6: 提交**

```bash
git add mindclaw/tools/base.py mindclaw/tools/registry.py tests/test_tools_base.py
git commit -m "feat(phase2): tool base class and registry"
```

---

### Task 2.2: 文件操作工具 (read_file, write_file, edit_file, list_dir)

**Files:**
- Create: `mindclaw/tools/file_ops.py`
- Test: `tests/test_tools_file_ops.py`

**Step 1: 写失败测试**

`tests/test_tools_file_ops.py`:
```python
# input: mindclaw.tools.file_ops
# output: 文件操作工具测试
# pos: 工具层文件操作测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from pathlib import Path


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作空间"""
    (tmp_path / "test.txt").write_text("hello world")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested content")
    return tmp_path


@pytest.mark.asyncio
async def test_read_file(workspace):
    from mindclaw.tools.file_ops import ReadFileTool

    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "test.txt"})
    assert "hello world" in result


@pytest.mark.asyncio
async def test_read_file_not_found(workspace):
    from mindclaw.tools.file_ops import ReadFileTool

    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "nonexistent.txt"})
    assert "not found" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_read_file_path_traversal(workspace):
    from mindclaw.tools.file_ops import ReadFileTool

    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "../../etc/passwd"})
    assert "denied" in result.lower() or "outside" in result.lower()


@pytest.mark.asyncio
async def test_write_file(workspace):
    from mindclaw.tools.file_ops import WriteFileTool

    tool = WriteFileTool(workspace=workspace)
    result = await tool.execute({"path": "new.txt", "content": "new content"})
    assert "success" in result.lower() or "written" in result.lower()
    assert (workspace / "new.txt").read_text() == "new content"


@pytest.mark.asyncio
async def test_write_file_creates_dirs(workspace):
    from mindclaw.tools.file_ops import WriteFileTool

    tool = WriteFileTool(workspace=workspace)
    await tool.execute({"path": "deep/nested/file.txt", "content": "deep"})
    assert (workspace / "deep" / "nested" / "file.txt").read_text() == "deep"


@pytest.mark.asyncio
async def test_list_dir(workspace):
    from mindclaw.tools.file_ops import ListDirTool

    tool = ListDirTool(workspace=workspace)
    result = await tool.execute({"path": "."})
    assert "test.txt" in result
    assert "subdir" in result


@pytest.mark.asyncio
async def test_edit_file(workspace):
    from mindclaw.tools.file_ops import EditFileTool

    tool = EditFileTool(workspace=workspace)
    result = await tool.execute({
        "path": "test.txt",
        "old_text": "hello world",
        "new_text": "hello mindclaw",
    })
    assert "success" in result.lower() or "edited" in result.lower()
    assert (workspace / "test.txt").read_text() == "hello mindclaw"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_tools_file_ops.py -v
```

**Step 3: 实现 tools/file_ops.py**

`mindclaw/tools/file_ops.py`:
```python
# input: tools/base.py, pathlib
# output: 导出 ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
# pos: 文件操作工具集，带路径沙箱保护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path

from .base import Tool, RiskLevel


def _safe_resolve(workspace: Path, relative_path: str) -> Path | None:
    """安全解析路径，防止路径遍历攻击"""
    try:
        target = (workspace / relative_path).resolve()
        if not str(target).startswith(str(workspace.resolve())):
            return None
        return target
    except (ValueError, OSError):
        return None


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
        },
        "required": ["path"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: file not found: {params['path']}"
        if not target.is_file():
            return f"Error: not a file: {params['path']}"
        try:
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file. Creates parent directories if needed. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(params["content"], encoding="utf-8")
            return f"Successfully written to {params['path']}"
        except Exception as e:
            return f"Error writing file: {e}"


class EditFileTool(Tool):
    name = "edit_file"
    description = "Edit a file by replacing old_text with new_text. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "old_text": {"type": "string", "description": "Text to find"},
            "new_text": {"type": "string", "description": "Replacement text"},
        },
        "required": ["path", "old_text", "new_text"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: file not found: {params['path']}"
        try:
            content = target.read_text(encoding="utf-8")
            if params["old_text"] not in content:
                return f"Error: old_text not found in {params['path']}"
            new_content = content.replace(params["old_text"], params["new_text"], 1)
            target.write_text(new_content, encoding="utf-8")
            return f"Successfully edited {params['path']}"
        except Exception as e:
            return f"Error editing file: {e}"


class ListDirTool(Tool):
    name = "list_dir"
    description = "List contents of a directory. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative directory path (default: '.')"},
        },
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        rel_path = params.get("path", ".")
        target = _safe_resolve(self.workspace, rel_path)
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: directory not found: {rel_path}"
        if not target.is_dir():
            return f"Error: not a directory: {rel_path}"
        try:
            entries = sorted(target.iterdir())
            lines = []
            for entry in entries:
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"  {entry.name}{suffix}")
            return f"Contents of {rel_path}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing directory: {e}"
```

**Step 4: 运行测试**

```bash
pytest tests/test_tools_file_ops.py -v
```

Expected: 全部 PASSED

**Step 5: 提交**

```bash
git add mindclaw/tools/file_ops.py tests/test_tools_file_ops.py
git commit -m "feat(phase2): file operation tools with path sandboxing"
```

---

### Task 2.3: Shell 执行工具

**Files:**
- Create: `mindclaw/tools/shell.py`
- Test: `tests/test_tools_shell.py`

**Step 1: 写失败测试**

`tests/test_tools_shell.py`:
```python
# input: mindclaw.tools.shell
# output: Shell 工具测试
# pos: 工具层 Shell 执行测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


@pytest.mark.asyncio
async def test_exec_simple_command(tmp_path):
    from mindclaw.tools.shell import ExecTool

    tool = ExecTool(workspace=tmp_path, timeout=10)
    result = await tool.execute({"command": "echo hello"})
    assert "hello" in result


@pytest.mark.asyncio
async def test_exec_deny_pattern():
    from mindclaw.tools.shell import ExecTool
    from pathlib import Path

    tool = ExecTool(workspace=Path("/tmp"), timeout=10)
    result = await tool.execute({"command": "rm -rf /"})
    assert "denied" in result.lower() or "blocked" in result.lower()


@pytest.mark.asyncio
async def test_exec_deny_fork_bomb():
    from mindclaw.tools.shell import ExecTool
    from pathlib import Path

    tool = ExecTool(workspace=Path("/tmp"), timeout=10)
    result = await tool.execute({"command": ":(){ :|:& };:"})
    assert "denied" in result.lower() or "blocked" in result.lower()


@pytest.mark.asyncio
async def test_exec_timeout(tmp_path):
    from mindclaw.tools.shell import ExecTool

    tool = ExecTool(workspace=tmp_path, timeout=1)
    result = await tool.execute({"command": "sleep 10"})
    assert "timeout" in result.lower()


@pytest.mark.asyncio
async def test_exec_returns_stderr(tmp_path):
    from mindclaw.tools.shell import ExecTool

    tool = ExecTool(workspace=tmp_path, timeout=10)
    result = await tool.execute({"command": "ls /nonexistent_dir_12345"})
    # 应包含错误信息
    assert len(result) > 0
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_tools_shell.py -v
```

**Step 3: 实现 tools/shell.py**

`mindclaw/tools/shell.py`:
```python
# input: tools/base.py, asyncio, re
# output: 导出 ExecTool
# pos: Shell 执行工具，含命令黑名单和超时保护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import re
from pathlib import Path

from loguru import logger

from .base import Tool, RiskLevel

DENY_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r"mkfs\.",
    r":\(\)\{.*\}",
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777\s+/",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
]

_compiled_deny = [re.compile(p) for p in DENY_PATTERNS]


def _is_denied(command: str) -> bool:
    for pattern in _compiled_deny:
        if pattern.search(command):
            return True
    return False


class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command and return its output. Use with caution."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        },
        "required": ["command"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, workspace: Path, timeout: int = 30) -> None:
        self.workspace = workspace
        self.timeout = timeout

    async def execute(self, params: dict) -> str:
        command = params["command"]

        if _is_denied(command):
            logger.warning(f"Blocked denied command: {command}")
            return f"Error: command denied by security policy"

        logger.info(f"Executing: {command}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = ""
            if output:
                result += output
            if errors:
                result += f"\nSTDERR:\n{errors}" if result else errors
            if not result:
                result = f"(exit code: {proc.returncode})"

            return result.strip()

        except asyncio.TimeoutError:
            logger.warning(f"Command timeout after {self.timeout}s: {command}")
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return f"Error: command timeout after {self.timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
```

**Step 4: 运行测试**

```bash
pytest tests/test_tools_shell.py -v
```

Expected: 全部 PASSED

**Step 5: 提交**

```bash
git add mindclaw/tools/shell.py tests/test_tools_shell.py
git commit -m "feat(phase2): shell exec tool with deny patterns and timeout"
```

---

### Task 2.4: 网页搜索 + 抓取工具

**Files:**
- Create: `mindclaw/tools/web.py`
- Test: `tests/test_tools_web.py`

**Step 1: 写失败测试**

`tests/test_tools_web.py`:
```python
# input: mindclaw.tools.web
# output: 网页工具测试
# pos: 工具层网页操作测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_web_fetch_returns_content():
    from mindclaw.tools.web import WebFetchTool

    tool = WebFetchTool()

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Hello World</p></body></html>"
    mock_response.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await tool.execute({"url": "https://example.com"})

    assert "Hello World" in result


@pytest.mark.asyncio
async def test_web_fetch_truncates_long_content():
    from mindclaw.tools.web import WebFetchTool

    tool = WebFetchTool(max_chars=100)

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>" + "x" * 1000 + "</p></body></html>"
    mock_response.headers = {"content-type": "text/html"}

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await tool.execute({"url": "https://example.com"})

    assert len(result) <= 150  # 100 + some overhead for truncation message


@pytest.mark.asyncio
async def test_web_search_returns_results():
    from mindclaw.tools.web import WebSearchTool

    tool = WebSearchTool(api_key="test-key")

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"title": "Result 1", "url": "https://a.com", "description": "Desc 1"},
                {"title": "Result 2", "url": "https://b.com", "description": "Desc 2"},
            ]
        }
    }

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await tool.execute({"query": "python asyncio"})

    assert "Result 1" in result
    assert "https://a.com" in result
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_tools_web.py -v
```

**Step 3: 实现 tools/web.py**

`mindclaw/tools/web.py`:
```python
# input: tools/base.py, httpx
# output: 导出 WebSearchTool, WebFetchTool
# pos: 网页搜索和抓取工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re

import httpx
from loguru import logger

from .base import Tool, RiskLevel


def _html_to_text(html: str) -> str:
    """简易 HTML 转纯文本"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a web page and return its text content."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, max_chars: int = 5000) -> None:
        self.max_chars = max_chars

    async def execute(self, params: dict) -> str:
        url = params["url"]
        logger.info(f"Fetching: {url}")

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=15.0
            ) as client:
                resp = await client.get(url)

            if resp.status_code != 200:
                return f"Error: HTTP {resp.status_code}"

            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                text = _html_to_text(resp.text)
            else:
                text = resp.text

            if len(text) > self.max_chars:
                text = text[: self.max_chars] + "\n...(truncated)"

            return text

        except Exception as e:
            return f"Error fetching URL: {e}"


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using Brave Search API."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def execute(self, params: dict) -> str:
        query = params["query"]
        count = params.get("count", 5)

        if not self.api_key:
            return "Error: web search API key not configured"

        logger.info(f"Searching: {query}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": count},
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": self.api_key,
                    },
                )

            if resp.status_code != 200:
                return f"Error: search API returned HTTP {resp.status_code}"

            data = resp.json()
            results = data.get("web", {}).get("results", [])

            if not results:
                return "No results found."

            lines = []
            for r in results:
                lines.append(f"**{r['title']}**")
                lines.append(f"  URL: {r['url']}")
                lines.append(f"  {r.get('description', '')}")
                lines.append("")

            return "\n".join(lines).strip()

        except Exception as e:
            return f"Error searching: {e}"
```

**Step 4: 运行测试**

```bash
pytest tests/test_tools_web.py -v
```

Expected: 全部 PASSED

**Step 5: 提交**

```bash
git add mindclaw/tools/web.py tests/test_tools_web.py
git commit -m "feat(phase2): web search and fetch tools"
```

---

### Task 2.5: Agent Loop 集成工具调用 (ReAct 循环)

**Files:**
- Modify: `mindclaw/orchestrator/agent_loop.py`
- Test: `tests/test_agent_loop_tools.py`

**Step 1: 写失败测试**

`tests/test_agent_loop_tools.py`:
```python
# input: mindclaw.orchestrator, mindclaw.tools
# output: Agent Loop 工具集成测试
# pos: 编排层工具调用集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import LLMRouter, ChatResult
from mindclaw.tools.base import Tool, RiskLevel
from mindclaw.tools.registry import ToolRegistry


class FakeReadTool(Tool):
    name = "read_file"
    description = "Read a file"
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    risk_level = RiskLevel.SAFE

    async def execute(self, params: dict) -> str:
        return "file content: hello world"


@pytest.mark.asyncio
async def test_agent_loop_with_tool_call():
    """Agent 应执行工具调用并将结果返回 LLM"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeReadTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="read test.txt"
    )

    # 第一次 LLM 调用: 返回工具调用
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = json.dumps({"path": "test.txt"})

    call_1 = ChatResult(content=None, tool_calls=[mock_tool_call])
    # 第二次 LLM 调用: 返回最终回复
    call_2 = ChatResult(content="The file contains: hello world", tool_calls=None)

    call_count = 0

    async def mock_chat(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return call_1
        return call_2

    with patch.object(router, "chat", side_effect=mock_chat):
        await agent.handle_message(inbound)

    outbound = await bus.get_outbound()
    assert "hello world" in outbound.text
    assert call_count == 2


@pytest.mark.asyncio
async def test_agent_loop_max_iterations():
    """Agent 应在达到最大迭代次数后停止"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig(agent={"maxIterations": 3})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeReadTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="loop forever"
    )

    # 每次都返回工具调用，永不停止
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = json.dumps({"path": "test.txt"})

    infinite_call = ChatResult(content=None, tool_calls=[mock_tool_call])

    with patch.object(router, "chat", return_value=infinite_call):
        await agent.handle_message(inbound)

    outbound = await bus.get_outbound()
    assert "max iterations" in outbound.text.lower() or "iteration" in outbound.text.lower()
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_agent_loop_tools.py -v
```

**Step 3: 更新 orchestrator/agent_loop.py**

`mindclaw/orchestrator/agent_loop.py` (完整替换):
```python
# input: bus/queue.py, bus/events.py, llm/router.py, config/schema.py, tools/registry.py
# output: 导出 AgentLoop
# pos: 编排层核心，ReAct 推理循环 (含工具调用)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import LLMRouter
from mindclaw.tools.registry import ToolRegistry

SYSTEM_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message.
"""


class AgentLoop:
    def __init__(
        self,
        config: MindClawConfig,
        bus: MessageBus,
        router: LLMRouter,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        self.tool_registry = tool_registry or ToolRegistry()
        self._sessions: dict[str, list[dict]] = {}

    def _get_history(self, session_key: str) -> list[dict]:
        if session_key not in self._sessions:
            self._sessions[session_key] = []
        return self._sessions[session_key]

    def _build_messages(self, history: list[dict], user_text: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    async def _execute_tool(self, name: str, arguments: str) -> str:
        tool = self.tool_registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            params = json.loads(arguments)
            result = await tool.execute(params)
            # 截断过长的结果
            max_chars = self.config.tools.tool_result_max_chars
            if len(result) > max_chars:
                result = result[:max_chars] + "\n...(truncated)"
            return result
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for tool '{name}'"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key
        history = self._get_history(session_key)
        max_iterations = self.config.agent.max_iterations

        messages = self._build_messages(history, inbound.text)
        tools = self.tool_registry.to_openai_tools() or None

        logger.info(f"Agent processing: session={session_key}, user={inbound.username}")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            result = await self.router.chat(messages=messages, tools=tools)

            # 无工具调用 → 返回最终回复
            if not result.tool_calls:
                reply_text = result.content or "(no response)"
                break

            # 处理工具调用
            # 添加 assistant 的工具调用消息
            assistant_msg = {"role": "assistant", "content": result.content, "tool_calls": []}
            for tc in result.tool_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append(assistant_msg)

            # 执行每个工具并添加结果
            for tc in result.tool_calls:
                logger.info(f"Tool call: {tc.function.name}")
                tool_result = await self._execute_tool(tc.function.name, tc.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            # 达到最大迭代次数
            reply_text = f"I reached the max iterations ({max_iterations}) and couldn't complete the task."

        # 保存到历史 (只保存用户消息和最终回复)
        history.append({"role": "user", "content": inbound.text})
        history.append({"role": "assistant", "content": reply_text})

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            text=reply_text,
        )
        await self.bus.put_outbound(outbound)
        logger.info(f"Agent replied: session={session_key}, iterations={iteration}")
```

**Step 4: 运行全部测试**

```bash
pytest tests/test_agent_loop.py tests/test_agent_loop_tools.py -v
```

Expected: 全部 PASSED (Task 1.4 的旧测试也需通过，因为 tool_registry 是 optional)

**Step 5: 提交**

```bash
git add mindclaw/orchestrator/agent_loop.py tests/test_agent_loop_tools.py
git commit -m "feat(phase2): agent loop with ReAct tool calling integration"
```

---

### Task 2.6: CLI 命令集成工具注册

**Files:**
- Modify: `mindclaw/cli/commands.py`

**Step 1: 更新 cli/commands.py 中的 _run_chat 函数**

在 `_run_chat` 中注册所有工具:

```python
# 在创建 agent 之前添加工具注册
from mindclaw.tools.registry import ToolRegistry
from mindclaw.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from mindclaw.tools.shell import ExecTool
from mindclaw.tools.web import WebFetchTool, WebSearchTool

workspace = Path.cwd()

registry = ToolRegistry()
registry.register(ReadFileTool(workspace=workspace))
registry.register(WriteFileTool(workspace=workspace))
registry.register(EditFileTool(workspace=workspace))
registry.register(ListDirTool(workspace=workspace))
registry.register(ExecTool(workspace=workspace, timeout=config.tools.exec_timeout))
registry.register(WebFetchTool())

# web_search 需要 API key
brave_key = config.providers.get("brave", None)
if brave_key and brave_key.api_key:
    registry.register(WebSearchTool(api_key=brave_key.api_key))

agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)
```

**Step 2: 运行全部测试**

```bash
pytest tests/ -v
```

Expected: 全部 PASSED

**Step 3: 手动集成测试**

```bash
export ANTHROPIC_API_KEY="your-key"
mindclaw chat
# 输入: "列出当前目录的文件"
# 期望: AI 调用 list_dir 工具，返回文件列表
# 输入: "帮我读取 pyproject.toml 的内容"
# 期望: AI 调用 read_file 工具，返回文件内容
# 输入: "执行 python --version"
# 期望: AI 调用 exec 工具，返回 Python 版本
# 输入: "exit"
```

**Step 4: 提交**

```bash
git add mindclaw/cli/commands.py
git commit -m "feat(phase2): register all tools in CLI command"
```

---

### Task 2.7: Phase 2 里程碑验证

**Step 1: 运行全部测试**

```bash
pytest tests/ -v --tb=short
```

Expected: 全部 PASSED

**Step 2: Ruff 检查**

```bash
ruff check mindclaw/ tests/
```

Expected: 无错误

**Step 3: 端到端工具调用验证**

```bash
export ANTHROPIC_API_KEY="your-key"
mindclaw chat
```

验证以下场景:
1. 文件读取: "读取 pyproject.toml"
2. 文件写入: "创建一个 hello.txt，内容是 Hello MindClaw"
3. 目录列表: "列出当前目录"
4. Shell 执行: "运行 date 命令"
5. 网页抓取: "抓取 https://example.com 的内容"

**Step 4: 创建/更新所有 _ARCHITECTURE.md**

为每个修改过的文件夹创建或更新 `_ARCHITECTURE.md`。

**Step 5: 提交里程碑**

```bash
git add -A
git commit -m "milestone(phase2): tool system complete - AI can read files, search web, execute commands"
```

---

## Phase 3-10 粗略路线图

以下阶段在 Phase 2 完成后再详细规划:

| Phase | 核心内容 | 关键依赖 |
|-------|---------|---------|
| **3: 安全层** | 审批工作流 + 命令沙箱 + 工具风险拦截 | Phase 2 工具系统 |
| **4: 记忆系统** | Session JSONL + MEMORY.md + HISTORY.md + 记忆整合 | Phase 1 Agent Loop |
| **5: Gateway + Telegram** | WebSocket Server + Token 认证 + Telegram Channel | Phase 1 渠道抽象 |
| **6: 编排层** | ACP 进程隔离 + 子 Agent + 并行任务 | Phase 2 工具 + Phase 3 安全 |
| **7: 插件系统** | manifest.json + 动态加载 + Hook | Phase 2 工具 Registry |
| **8: 更多渠道** | Slack + 飞书 + Discord | Phase 5 渠道架构 |
| **9: 知识管理** | Obsidian + Notion + 网页收藏 + LanceDB | Phase 4 记忆系统 |
| **10: 高级功能** | 微信 + 技能系统 + Cron + 多模型降级 + 守护进程 | 全部 |

---

## 总结

| 指标 | Phase 0 | Phase 1 | Phase 2 |
|------|---------|---------|---------|
| **Task 数** | 4 | 7 | 7 |
| **新文件** | ~15 | ~8 | ~6 |
| **测试文件** | 1 | 3 | 4 |
| **里程碑** | `import mindclaw` | CLI 对话 | 工具调用 |
