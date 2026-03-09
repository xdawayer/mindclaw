# input: mindclaw.knowledge.memory, mindclaw.knowledge.session, mindclaw.llm.router
# output: MemoryManager 测试
# pos: 验证 LLM 驱动记忆整合流程
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

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
    return LLMRouter(config)


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
    assert manager.should_consolidate(20) is False  # not exceeded, equal
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
    assert (data_dir / "MEMORY.md").exists()
    assert "15 test messages" in (data_dir / "MEMORY.md").read_text()
    assert (data_dir / "HISTORY.md").exists()
    assert "整合" in (data_dir / "HISTORY.md").read_text()
    loaded, total = store.load("cli:local")
    assert total == 25
    assert len(loaded) == 10  # keep_recent=10


@pytest.mark.asyncio
async def test_consolidate_with_existing_memory(manager, store, data_dir):
    (data_dir / "MEMORY.md").write_text("# old\n- old fact\n")
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
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(8)]
    store.append("cli:local", messages)
    result = await manager.consolidate("cli:local", store)
    assert result is False


@pytest.mark.asyncio
async def test_consolidate_llm_failure(manager, store, data_dir):
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
    assert not (data_dir / "MEMORY.md").exists()
