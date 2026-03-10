# input: knowledge/memory.py, knowledge/vector.py, orchestrator/context.py
# output: 向量搜索集成测试 (consolidation 触发索引 + context builder 注入)
# pos: Phase 10 向量搜索集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Integration tests for vector search: consolidation indexing + context injection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.config.schema import MindClawConfig, VectorDbConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.knowledge.vector import VectorStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.context import ContextBuilder

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config() -> MindClawConfig:
    return MindClawConfig()


@pytest.fixture
def mock_router() -> MagicMock:
    router = MagicMock(spec=LLMRouter)
    return router


@pytest.fixture
def vector_store(data_dir: Path) -> VectorStore:
    vc = VectorDbConfig(enabled=True, chunk_size=200, top_k=3)
    return VectorStore(data_dir=data_dir, config=vc)


@pytest.fixture
def memory_manager(data_dir: Path, mock_router: MagicMock, config: MindClawConfig) -> MemoryManager:
    return MemoryManager(data_dir=data_dir, router=mock_router, config=config)


# ── ContextBuilder with vector store tests ────────────────


async def test_context_builder_with_vector_search(
    memory_manager: MemoryManager, vector_store: VectorStore
) -> None:
    """ContextBuilder should inject semantic search results when vector store is provided."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        await vector_store.index_document(
            "User prefers dark mode and vim",
            source="MEMORY.md",
            doc_type="memory",
        )

        builder = ContextBuilder(
            memory_manager=memory_manager,
            vector_store=vector_store,
        )
        prompt = await builder.abuild_system_prompt(user_message="What theme do I prefer?")

    assert "MindClaw" in prompt  # base prompt
    assert "Relevant Context" in prompt or "dark mode" in prompt


async def test_context_builder_without_vector_is_sync_compatible(
    memory_manager: MemoryManager,
) -> None:
    """ContextBuilder without vector store should still work (backward compat)."""
    builder = ContextBuilder(memory_manager=memory_manager)
    # Sync call still works
    prompt = builder.build_system_prompt()
    assert "MindClaw" in prompt
    # Async call also works
    prompt2 = await builder.abuild_system_prompt()
    assert "MindClaw" in prompt2


async def test_context_builder_async_without_user_message(
    memory_manager: MemoryManager, vector_store: VectorStore
) -> None:
    """Async call without user_message should not trigger vector search."""
    builder = ContextBuilder(
        memory_manager=memory_manager,
        vector_store=vector_store,
    )
    prompt = await builder.abuild_system_prompt()
    assert "MindClaw" in prompt
    # No "Relevant Context" section since no user_message
    assert "Relevant Context" not in prompt


# ── Consolidation triggers vector indexing ────────────────


async def test_consolidation_indexes_vector(
    data_dir: Path, config: MindClawConfig, vector_store: VectorStore
) -> None:
    """After consolidation, MEMORY.md content should be indexed in vector store."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    # Set up router to return consolidation result
    mock_router = MagicMock(spec=LLMRouter)
    mock_chat_result = MagicMock()
    mock_chat_result.content = "# MindClaw Memory\n\n## 关键事实\n- User likes Python\n"
    mock_router.chat = AsyncMock(return_value=mock_chat_result)

    mm = MemoryManager(
        data_dir=data_dir, router=mock_router, config=config, vector_store=vector_store
    )

    # Set up session with enough messages
    session_store = SessionStore(data_dir=data_dir)
    for i in range(25):
        session_store.append("test", [{"role": "user", "content": f"msg {i}"}])

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        success = await mm.consolidate("test", session_store)

    assert success
    # Vector store should have been indexed
    assert await vector_store.count() >= 1
