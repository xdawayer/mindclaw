# Phase 4: 记忆系统 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 MindClaw 重启后记住对话历史和用户偏好，通过 Session JSONL 持久化 + LLM 驱动的记忆整合实现长期记忆。

**Architecture:** `knowledge/session.py` 提供 JSONL 读写持久化，`knowledge/memory.py` 提供 LLM 驱动的记忆整合（MEMORY.md + HISTORY.md），`orchestrator/context.py` 动态构建系统提示注入记忆。AgentLoop 直接调用这些模块，不引入额外抽象层。

**Tech Stack:** Python 3.12+ / asyncio / Pydantic / loguru / pytest + pytest-asyncio

**Design doc:** `docs/plans/2026-03-08-phase4-memory-system-design.md`

---

### Task 1: KnowledgeConfig 配置

**Files:**
- Modify: `mindclaw/config/schema.py:51-68`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

在 `tests/test_config.py` 末尾添加：

```python
def test_knowledge_config_defaults():
    from mindclaw.config.schema import KnowledgeConfig

    kc = KnowledgeConfig()
    assert kc.data_dir == "data"
    assert kc.consolidation_threshold == 20
    assert kc.consolidation_keep_recent == 10


def test_mindclaw_config_has_knowledge():
    config = MindClawConfig()
    assert hasattr(config, "knowledge")
    assert config.knowledge.data_dir == "data"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_knowledge_config_defaults tests/test_config.py::test_mindclaw_config_has_knowledge -v`
Expected: FAIL with "cannot import name 'KnowledgeConfig'"

**Step 3: Write minimal implementation**

在 `mindclaw/config/schema.py` 中，在 `SecurityConfig` 之后添加：

```python
class KnowledgeConfig(BaseModel):
    data_dir: str = Field(default="data", alias="dataDir")
    consolidation_threshold: int = Field(default=20, alias="consolidationThreshold")
    consolidation_keep_recent: int = Field(default=10, alias="consolidationKeepRecent")

    model_config = {"populate_by_name": True}
```

在 `MindClawConfig` 中添加字段：

```python
knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
```

更新文件头注释的 `output` 行，添加 `KnowledgeConfig`。

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add mindclaw/config/schema.py tests/test_config.py
git commit -m "feat(phase4): add KnowledgeConfig to configuration schema"
```

---

### Task 2: SessionStore — JSONL 持久化

**Files:**
- Create: `mindclaw/knowledge/session.py`
- Create: `tests/test_session_store.py`

**Step 1: Write the failing tests**

创建 `tests/test_session_store.py`：

```python
# input: mindclaw.knowledge.session
# output: SessionStore 测试
# pos: 验证 JSONL 持久化和整合指针
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from pathlib import Path

import pytest

from mindclaw.knowledge.session import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(data_dir=tmp_path)


def test_append_and_load(store, tmp_path):
    """Append messages then load them back."""
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    store.append("cli:local", messages)

    loaded, total = store.load("cli:local")
    assert len(loaded) == 2
    assert total == 2
    assert loaded[0]["role"] == "user"
    assert loaded[1]["content"] == "hi there"


def test_load_empty_session(store):
    """Loading a non-existent session returns empty list."""
    loaded, total = store.load("cli:nonexistent")
    assert loaded == []
    assert total == 0


def test_append_multiple_times(store):
    """Multiple appends accumulate messages."""
    store.append("cli:local", [{"role": "user", "content": "msg1"}])
    store.append("cli:local", [{"role": "assistant", "content": "reply1"}])
    store.append("cli:local", [{"role": "user", "content": "msg2"}])

    loaded, total = store.load("cli:local")
    assert len(loaded) == 3
    assert total == 3


def test_mark_consolidated_and_load(store):
    """After consolidation, load only returns unconsolidated messages."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
    store.append("cli:local", messages)

    store.mark_consolidated("cli:local", pointer=3)

    loaded, total = store.load("cli:local")
    assert len(loaded) == 2  # msg3, msg4 (0-indexed: items at index 3,4)
    assert total == 5
    assert loaded[0]["content"] == "msg3"
    assert loaded[1]["content"] == "msg4"


def test_mark_consolidated_twice(store):
    """Second consolidation moves pointer further."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    store.append("cli:local", messages)

    store.mark_consolidated("cli:local", pointer=3)
    store.mark_consolidated("cli:local", pointer=7)

    loaded, total = store.load("cli:local")
    assert len(loaded) == 3  # msg7, msg8, msg9
    assert total == 10


def test_session_key_to_filename(store):
    """Session key is sanitized for filesystem use."""
    store.append("telegram:12345", [{"role": "user", "content": "hi"}])
    loaded, total = store.load("telegram:12345")
    assert len(loaded) == 1


def test_load_returns_messages_for_consolidation(store):
    """load_for_consolidation returns messages in the consolidation window."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)

    # With keep_recent=10, consolidation window is messages 0-14
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert len(to_consolidate) == 15
    assert to_consolidate[0]["content"] == "msg0"
    assert to_consolidate[-1]["content"] == "msg14"


def test_load_for_consolidation_with_existing_pointer(store):
    """Consolidation window starts after previous pointer."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)
    store.mark_consolidated("cli:local", pointer=5)

    # pointer=5, keep_recent=10, so window is messages 5-14
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert len(to_consolidate) == 10
    assert to_consolidate[0]["content"] == "msg5"
    assert to_consolidate[-1]["content"] == "msg14"


def test_load_for_consolidation_not_enough_messages(store):
    """If not enough messages beyond keep_recent, return empty."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(8)]
    store.append("cli:local", messages)

    # keep_recent=10, only 8 messages total → nothing to consolidate
    to_consolidate = store.load_for_consolidation("cli:local", keep_recent=10)
    assert to_consolidate == []
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_session_store.py -v`
Expected: FAIL with "No module named 'mindclaw.knowledge.session'"

**Step 3: Write minimal implementation**

创建 `mindclaw/knowledge/session.py`：

```python
# input: pathlib, json
# output: 导出 SessionStore
# pos: Session JSONL 持久化，管理对话历史的磁盘读写和整合指针
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from pathlib import Path

from loguru import logger

_META_CONSOLIDATION = "consolidation"


class SessionStore:
    """JSONL-based session persistence with consolidation pointer."""

    def __init__(self, data_dir: Path) -> None:
        self._sessions_dir = Path(data_dir) / "sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_key: str) -> Path:
        safe_name = session_key.replace(":", "_").replace("/", "_")
        return self._sessions_dir / f"{safe_name}.jsonl"

    def _read_lines(self, session_key: str) -> tuple[list[dict], int]:
        """Read all message lines and current consolidation pointer.

        Returns (all_messages, pointer). Messages do NOT include meta lines.
        """
        path = self._session_path(session_key)
        if not path.exists():
            return [], 0

        messages: list[dict] = []
        pointer = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Skipping malformed line in {path}")
                continue
            if obj.get("_meta") == _META_CONSOLIDATION:
                pointer = obj.get("pointer", 0)
            else:
                messages.append(obj)
        return messages, pointer

    def load(self, session_key: str) -> tuple[list[dict], int]:
        """Load unconsolidated messages for a session.

        Returns (unconsolidated_messages, total_message_count).
        """
        messages, pointer = self._read_lines(session_key)
        return messages[pointer:], len(messages)

    def append(self, session_key: str, messages: list[dict]) -> None:
        """Append messages to the session JSONL file."""
        if not messages:
            return
        path = self._session_path(session_key)
        with path.open("a", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def mark_consolidated(self, session_key: str, pointer: int) -> None:
        """Update the consolidation pointer by appending a meta line."""
        path = self._session_path(session_key)
        meta = {"_meta": _META_CONSOLIDATION, "pointer": pointer}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(meta) + "\n")
        logger.info(f"Session {session_key}: consolidated up to message {pointer}")

    def load_for_consolidation(
        self, session_key: str, keep_recent: int = 10
    ) -> list[dict]:
        """Return messages in the consolidation window.

        Window = messages[pointer : total - keep_recent].
        If window is empty or negative, returns [].
        """
        messages, pointer = self._read_lines(session_key)
        total = len(messages)
        end = total - keep_recent
        if end <= pointer:
            return []
        return messages[pointer:end]
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_session_store.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS (77 existing + 9 new = 86)

**Step 6: Commit**

```bash
git add mindclaw/knowledge/session.py tests/test_session_store.py
git commit -m "feat(phase4): add SessionStore with JSONL persistence and consolidation pointer"
```

---

### Task 3: MemoryManager — LLM 驱动记忆整合

**Files:**
- Create: `mindclaw/knowledge/memory.py`
- Create: `tests/test_memory_manager.py`

**Step 1: Write the failing tests**

创建 `tests/test_memory_manager.py`：

```python
# input: mindclaw.knowledge.memory, mindclaw.knowledge.session
# output: MemoryManager 测试
# pos: 验证记忆整合逻辑（使用 mock LLM）
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import ChatResult, LLMRouter


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def config():
    return MindClawConfig()


@pytest.fixture
def mock_router(config):
    router = LLMRouter(config)
    return router


@pytest.fixture
def store(data_dir):
    return SessionStore(data_dir=data_dir)


@pytest.fixture
def manager(data_dir, mock_router, config):
    return MemoryManager(data_dir=data_dir, router=mock_router, config=config)


def test_should_consolidate_true(manager):
    assert manager.should_consolidate(25) is True


def test_should_consolidate_false(manager):
    assert manager.should_consolidate(15) is False


def test_should_consolidate_boundary(manager):
    # Exactly at threshold should not trigger (need to exceed)
    assert manager.should_consolidate(20) is False
    assert manager.should_consolidate(21) is True


def test_load_memory_empty(manager):
    assert manager.load_memory() == ""


def test_load_memory_existing(manager, data_dir):
    memory_path = data_dir / "MEMORY.md"
    memory_path.write_text("# MindClaw Memory\n\n## 用户偏好\n- likes Python\n")
    assert "likes Python" in manager.load_memory()


@pytest.mark.asyncio
async def test_consolidate_writes_memory_and_history(manager, store, data_dir):
    """Full consolidation flow with mocked LLM."""
    # Seed 25 messages
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)

    fake_memory = "# MindClaw Memory\n\n## 关键事实\n- User sent 15 test messages\n"
    with patch.object(
        manager._router,
        "chat",
        new_callable=AsyncMock,
        return_value=ChatResult(content=fake_memory, tool_calls=None),
    ):
        result = await manager.consolidate("cli:local", store)

    assert result is True

    # MEMORY.md should be written
    memory_path = data_dir / "MEMORY.md"
    assert memory_path.exists()
    assert "15 test messages" in memory_path.read_text()

    # HISTORY.md should be appended
    history_path = data_dir / "HISTORY.md"
    assert history_path.exists()
    assert "整合" in history_path.read_text()

    # Consolidation pointer should be updated
    loaded, total = store.load("cli:local")
    assert total == 25
    assert len(loaded) == 10  # keep_recent=10


@pytest.mark.asyncio
async def test_consolidate_with_existing_memory(manager, store, data_dir):
    """Consolidation merges with existing MEMORY.md."""
    # Write existing memory
    (data_dir / "MEMORY.md").write_text("# MindClaw Memory\n\n## 旧记忆\n- old fact\n")

    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)

    merged = "# MindClaw Memory\n\n## 旧记忆\n- old fact\n\n## 新记忆\n- new fact\n"
    with patch.object(
        manager._router,
        "chat",
        new_callable=AsyncMock,
        return_value=ChatResult(content=merged, tool_calls=None),
    ):
        result = await manager.consolidate("cli:local", store)

    assert result is True
    content = (data_dir / "MEMORY.md").read_text()
    assert "old fact" in content
    assert "new fact" in content


@pytest.mark.asyncio
async def test_consolidate_not_enough_messages(manager, store):
    """Consolidation is skipped if not enough messages."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(8)]
    store.append("cli:local", messages)

    result = await manager.consolidate("cli:local", store)
    assert result is False


@pytest.mark.asyncio
async def test_consolidate_llm_failure(manager, store, data_dir):
    """Consolidation handles LLM errors gracefully."""
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
    store.append("cli:local", messages)

    with patch.object(
        manager._router,
        "chat",
        new_callable=AsyncMock,
        side_effect=Exception("LLM unavailable"),
    ):
        result = await manager.consolidate("cli:local", store)

    assert result is False
    # MEMORY.md should NOT be written on failure
    assert not (data_dir / "MEMORY.md").exists()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_memory_manager.py -v`
Expected: FAIL with "No module named 'mindclaw.knowledge.memory'"

**Step 3: Write minimal implementation**

创建 `mindclaw/knowledge/memory.py`：

```python
# input: knowledge/session.py, llm/router.py, config/schema.py
# output: 导出 MemoryManager
# pos: LLM 驱动的记忆整合，管理 MEMORY.md 和 HISTORY.md
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter

_CONSOLIDATION_PROMPT = """\
You are a memory manager for MindClaw, a personal AI assistant.

Your task: Extract important information from the conversation below and merge it with existing memory.

## Existing Memory
{existing_memory}

## Conversation to Process
{conversation}

## Instructions
1. Extract facts worth remembering long-term: user preferences, key facts, important decisions.
2. Merge with existing memory: keep what's still relevant, remove what's outdated, add new information.
3. Output the complete updated memory in this exact Markdown format:

```
# MindClaw Memory

## 用户偏好
- (user preferences, habits, communication style)

## 关键事实
- (key facts about the user, their projects, environment)

## 重要决定
- (important decisions, architectural choices, agreements)
```

Only output the Markdown content. No explanation or commentary.
"""


class MemoryManager:
    """LLM-driven memory consolidation with MEMORY.md and HISTORY.md."""

    def __init__(
        self, data_dir: Path, router: LLMRouter, config: MindClawConfig
    ) -> None:
        self._data_dir = Path(data_dir)
        self._router = router
        self._config = config
        self._memory_path = self._data_dir / "MEMORY.md"
        self._history_path = self._data_dir / "HISTORY.md"

    def should_consolidate(self, unconsolidated_count: int) -> bool:
        """Check if automatic consolidation should trigger."""
        return unconsolidated_count > self._config.knowledge.consolidation_threshold

    def load_memory(self) -> str:
        """Read MEMORY.md content. Returns empty string if not found."""
        if not self._memory_path.exists():
            return ""
        return self._memory_path.read_text(encoding="utf-8")

    async def consolidate(
        self, session_key: str, session_store: SessionStore
    ) -> bool:
        """Execute memory consolidation. Returns True if successful."""
        keep_recent = self._config.knowledge.consolidation_keep_recent
        to_consolidate = session_store.load_for_consolidation(
            session_key, keep_recent=keep_recent
        )
        if not to_consolidate:
            logger.debug(f"Session {session_key}: not enough messages to consolidate")
            return False

        existing_memory = self.load_memory() or "(no existing memory)"

        # Format conversation for LLM
        conversation_lines = []
        for msg in to_consolidate:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                conversation_lines.append(f"{role}: {content}")
        conversation = "\n".join(conversation_lines)

        prompt = _CONSOLIDATION_PROMPT.format(
            existing_memory=existing_memory,
            conversation=conversation,
        )

        try:
            result = await self._router.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            new_memory = result.content
            if not new_memory:
                logger.warning("LLM returned empty memory content")
                return False
        except Exception:
            logger.exception(f"Memory consolidation failed for {session_key}")
            return False

        # Write MEMORY.md
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._memory_path.write_text(new_memory, encoding="utf-8")
        logger.info(f"Updated MEMORY.md ({len(new_memory)} chars)")

        # Append to HISTORY.md
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{now}] 整合了 {len(to_consolidate)} 条消息 (session: {session_key})\n"
        with self._history_path.open("a", encoding="utf-8") as f:
            if not self._history_path.exists() or self._history_path.stat().st_size == 0:
                f.write("# MindClaw History\n\n")
            f.write(entry)

        # Update consolidation pointer
        all_messages, pointer = session_store._read_lines(session_key)
        new_pointer = len(all_messages) - keep_recent
        session_store.mark_consolidated(session_key, pointer=new_pointer)

        return True
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memory_manager.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS (86 existing + 9 new = 95)

**Step 6: Commit**

```bash
git add mindclaw/knowledge/memory.py tests/test_memory_manager.py
git commit -m "feat(phase4): add MemoryManager with LLM-driven consolidation"
```

---

### Task 4: ContextBuilder — 动态系统提示

**Files:**
- Create: `mindclaw/orchestrator/context.py`
- Create: `tests/test_context_builder.py`

**Step 1: Write the failing tests**

创建 `tests/test_context_builder.py`：

```python
# input: mindclaw.orchestrator.context, mindclaw.knowledge.memory
# output: ContextBuilder 测试
# pos: 验证系统提示动态构建
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path
from unittest.mock import MagicMock

from mindclaw.orchestrator.context import ContextBuilder


def test_build_system_prompt_without_memory():
    """System prompt should work even without any memory."""
    mm = MagicMock()
    mm.load_memory.return_value = ""
    builder = ContextBuilder(memory_manager=mm)

    prompt = builder.build_system_prompt()

    assert "MindClaw" in prompt
    assert "Current Date" in prompt


def test_build_system_prompt_with_memory():
    """System prompt includes memory when available."""
    mm = MagicMock()
    mm.load_memory.return_value = "# MindClaw Memory\n\n## 用户偏好\n- likes Python\n"
    builder = ContextBuilder(memory_manager=mm)

    prompt = builder.build_system_prompt()

    assert "MindClaw" in prompt
    assert "likes Python" in prompt
    assert "Memory" in prompt


def test_build_system_prompt_has_date():
    """System prompt includes current date."""
    mm = MagicMock()
    mm.load_memory.return_value = ""
    builder = ContextBuilder(memory_manager=mm)

    prompt = builder.build_system_prompt()

    # Should contain a date-like string (YYYY-MM-DD)
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2}", prompt)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_context_builder.py -v`
Expected: FAIL with "No module named 'mindclaw.orchestrator.context'"

**Step 3: Write minimal implementation**

创建 `mindclaw/orchestrator/context.py`：

```python
# input: knowledge/memory.py
# output: 导出 ContextBuilder
# pos: 动态构建系统提示，注入记忆和日期
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from datetime import date

from mindclaw.knowledge.memory import MemoryManager

_BASE_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message."""


class ContextBuilder:
    """Builds the system prompt dynamically, injecting memory and date."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    def build_system_prompt(self) -> str:
        parts = [_BASE_PROMPT]

        parts.append(f"\n\n## Current Date\n{date.today().isoformat()}")

        memory = self._memory_manager.load_memory()
        if memory.strip():
            parts.append(f"\n\n## Memory (what you know about the user)\n{memory}")

        return "".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_context_builder.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS (95 existing + 3 new = 98)

**Step 6: Commit**

```bash
git add mindclaw/orchestrator/context.py tests/test_context_builder.py
git commit -m "feat(phase4): add ContextBuilder for dynamic system prompt with memory injection"
```

---

### Task 5: AgentLoop 集成 — 持久化 + 整合 + 上下文

**Files:**
- Modify: `mindclaw/orchestrator/agent_loop.py`
- Modify: `tests/test_agent_loop.py`

这是最关键的集成任务。需要修改 AgentLoop 来：
1. 使用 SessionStore 替代内存 `_sessions` dict
2. 使用 ContextBuilder 替代硬编码 `SYSTEM_PROMPT`
3. 在消息处理后检查并触发自动整合

**Step 1: Write the failing tests**

在 `tests/test_agent_loop.py` 中添加新的集成测试：

```python
@pytest.mark.asyncio
async def test_agent_persists_session_to_store(bus, config):
    """AgentLoop should persist messages via SessionStore."""
    from mindclaw.knowledge.session import SessionStore

    store = SessionStore(data_dir=tmp_path)
    router = LLMRouter(config)

    agent = AgentLoop(
        config=config, bus=bus, router=router, session_store=store,
    )

    # Mock LLM
    with patch.object(router, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ChatResult(content="hello back", tool_calls=None)
        await agent.handle_message(make_inbound("hi"))

    loaded, total = store.load("cli:local")
    assert total >= 2  # at least user msg + assistant reply


@pytest.mark.asyncio
async def test_agent_uses_context_builder(bus, config):
    """AgentLoop should use ContextBuilder for system prompt."""
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)

    with patch.object(router, "chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ChatResult(content="reply", tool_calls=None)
        await agent.handle_message(make_inbound("test"))

    # Verify system prompt contains date (from ContextBuilder)
    call_args = mock_chat.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages") or call_args[0][0]
    system_msg = messages[0]
    assert "Current Date" in system_msg["content"]
```

注意：这些测试可能需要根据现有 test fixtures 调整。关键是验证 `SessionStore` 和 `ContextBuilder` 被正确调用。

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: FAIL (AgentLoop 尚未接受 session_store 参数)

**Step 3: Write the implementation**

修改 `mindclaw/orchestrator/agent_loop.py`：

1. 删除模块级 `SYSTEM_PROMPT` 常量
2. 导入 `SessionStore`, `MemoryManager`, `ContextBuilder`
3. `__init__` 新增可选参数 `session_store`, `memory_manager`, `context_builder`
4. 如果未传入，创建默认实例（使用 config.knowledge.data_dir）
5. `_get_history` 改为从 `SessionStore.load()` 加载
6. `_build_messages` 使用 `ContextBuilder.build_system_prompt()`
7. `handle_message` 结束时调用 `SessionStore.append()` 持久化
8. `handle_message` 结束时检查 `MemoryManager.should_consolidate()` 并触发

关键改动点：

```python
import json
from pathlib import Path

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.base import RiskLevel
from mindclaw.tools.registry import ToolRegistry

MAX_HISTORY_MESSAGES = 100


class AgentLoop:
    def __init__(
        self,
        config: MindClawConfig,
        bus: MessageBus,
        router: LLMRouter,
        tool_registry: ToolRegistry | None = None,
        approval_manager: ApprovalManager | None = None,
        session_store: SessionStore | None = None,
        memory_manager: MemoryManager | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        self.tool_registry = tool_registry or ToolRegistry()
        self.approval_manager = approval_manager

        data_dir = Path(config.knowledge.data_dir)
        self.session_store = session_store or SessionStore(data_dir=data_dir)
        self.memory_manager = memory_manager or MemoryManager(
            data_dir=data_dir, router=router, config=config,
        )
        self.context_builder = context_builder or ContextBuilder(
            memory_manager=self.memory_manager,
        )

        self._current_channel: str = ""
        self._current_chat_id: str = ""

    def _get_history(self, session_key: str) -> list[dict]:
        history, _ = self.session_store.load(session_key)
        if len(history) > MAX_HISTORY_MESSAGES:
            cutoff = max(0, len(history) - MAX_HISTORY_MESSAGES)
            while cutoff > 0 and history[cutoff].get("role") != "user":
                cutoff -= 1
            history = history[cutoff:]
        return history

    def _build_messages(self, history: list[dict], user_text: str) -> list[dict]:
        system_prompt = self.context_builder.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    # _execute_tool stays the same

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key
        self._current_channel = inbound.channel
        self._current_chat_id = inbound.chat_id
        history = self._get_history(session_key)
        initial_history_len = len(history)
        max_iterations = max(1, self.config.agent.max_iterations)

        messages = self._build_messages(history, inbound.text)
        tools = self.tool_registry.to_openai_tools() or None

        logger.info(f"Agent processing: session={session_key}, user={inbound.username}")

        try:
            # ... existing ReAct loop (unchanged) ...
            pass
        except Exception:
            raise  # session poisoning protection no longer needs history rollback
                   # since history is loaded from disk each time

        # Persist new messages to SessionStore
        new_messages = messages[1 + initial_history_len:]
        new_messages.append({"role": "assistant", "content": reply_text})
        self.session_store.append(session_key, new_messages)

        # Check for automatic consolidation
        _, total = self.session_store.load(session_key)
        if self.memory_manager.should_consolidate(total - self._get_pointer(session_key)):
            try:
                await self.memory_manager.consolidate(session_key, self.session_store)
            except Exception:
                logger.exception("Auto-consolidation failed")

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            text=reply_text,
        )
        await self.bus.put_outbound(outbound)
        logger.info(f"Agent replied: session={session_key}")
```

注意：session poisoning protection 现在更简单了 — 如果异常发生，新消息不会被 `append` 到 SessionStore，因为 `append` 在 try 之后。重启后从磁盘重新加载，自然没有损坏的数据。

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_loop.py -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add mindclaw/orchestrator/agent_loop.py tests/test_agent_loop.py
git commit -m "feat(phase4): integrate SessionStore, MemoryManager, ContextBuilder into AgentLoop"
```

---

### Task 6: CLI 入口集成

**Files:**
- Modify: `mindclaw/cli/commands.py:28-70`

**Step 1: Update _run_chat to create knowledge components**

在 `_run_chat` 中，在创建 `AgentLoop` 之前，添加：

```python
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.orchestrator.context import ContextBuilder

data_dir = Path(config.knowledge.data_dir)
session_store = SessionStore(data_dir=data_dir)
memory_manager = MemoryManager(data_dir=data_dir, router=router, config=config)
context_builder = ContextBuilder(memory_manager=memory_manager)
```

更新 `AgentLoop` 构造：

```python
agent = AgentLoop(
    config=config,
    bus=bus,
    router=router,
    tool_registry=registry,
    approval_manager=approval_manager,
    session_store=session_store,
    memory_manager=memory_manager,
    context_builder=context_builder,
)
```

**Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add mindclaw/cli/commands.py
git commit -m "feat(phase4): wire knowledge components into CLI entry point"
```

---

### Task 7: 文档更新

**Files:**
- Modify: `mindclaw/knowledge/_ARCHITECTURE.md`
- Modify: `mindclaw/orchestrator/_ARCHITECTURE.md`
- Modify: `mindclaw/config/_ARCHITECTURE.md` (如果 schema 改了)
- Modify: `CLAUDE.md` (Phase 进度更新)

**Step 1: Update _ARCHITECTURE.md files**

`mindclaw/knowledge/_ARCHITECTURE.md`:
```markdown
> 一旦本文件夹有任何文件变化（新增/删除/重命名/职责变更），请立即更新本文档。

知识层：Session JSONL 持久化 + LLM 驱动记忆整合（MEMORY.md / HISTORY.md）

| 文件 | 地位 | 功能 |
|------|------|------|
| `__init__.py` | 包标识 | 空 |
| `session.py` | 核心 | SessionStore — JSONL 文件读写，整合指针管理 |
| `memory.py` | 核心 | MemoryManager — LLM 驱动记忆整合，MEMORY.md + HISTORY.md 管理 |
```

`mindclaw/orchestrator/_ARCHITECTURE.md` 添加 `context.py` 条目。

`CLAUDE.md` 中 Phase 4 标记为已完成。

**Step 2: Commit**

```bash
git add -A
git commit -m "docs(phase4): update architecture docs and Phase progress"
```

---

## 任务依赖关系

```
Task 1 (KnowledgeConfig)
  ↓
Task 2 (SessionStore) ──→ Task 3 (MemoryManager) ──→ Task 4 (ContextBuilder)
                                                          ↓
                                                     Task 5 (AgentLoop 集成)
                                                          ↓
                                                     Task 6 (CLI 集成)
                                                          ↓
                                                     Task 7 (文档更新)
```

## 预期最终状态

- 77 → ~100+ tests
- 重启 `mindclaw chat` 后，之前的对话历史自动恢复
- 对话超过 20 条后自动整合记忆到 MEMORY.md
- 系统提示包含日期和记忆信息
- `data/sessions/` 包含 JSONL 文件
- `data/MEMORY.md` 和 `data/HISTORY.md` 在整合后存在
