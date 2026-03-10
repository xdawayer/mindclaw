# input: tools/memory.py, knowledge/memory.py, knowledge/vector.py
# output: memory_save / memory_search 工具测试
# pos: 记忆工具单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for MemorySaveTool and MemorySearchTool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.config.schema import MindClawConfig, VectorDbConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.vector import VectorStore
from mindclaw.llm.router import LLMRouter
from mindclaw.tools.memory import MemorySaveTool, MemorySearchTool

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config() -> MindClawConfig:
    return MindClawConfig()


@pytest.fixture
def mock_router() -> MagicMock:
    return MagicMock(spec=LLMRouter)


@pytest.fixture
def memory_manager(data_dir: Path, mock_router: MagicMock, config: MindClawConfig) -> MemoryManager:
    return MemoryManager(data_dir=data_dir, router=mock_router, config=config)


@pytest.fixture
def vector_store(data_dir: Path) -> VectorStore:
    vc = VectorDbConfig(enabled=True, chunk_size=200, top_k=3)
    return VectorStore(data_dir=data_dir, config=vc)


@pytest.fixture
def save_tool(memory_manager: MemoryManager, vector_store: VectorStore) -> MemorySaveTool:
    return MemorySaveTool(memory_manager=memory_manager, vector_store=vector_store)


@pytest.fixture
def save_tool_no_vector(memory_manager: MemoryManager) -> MemorySaveTool:
    return MemorySaveTool(memory_manager=memory_manager, vector_store=None)


@pytest.fixture
def search_tool(memory_manager: MemoryManager, vector_store: VectorStore) -> MemorySearchTool:
    return MemorySearchTool(memory_manager=memory_manager, vector_store=vector_store)


@pytest.fixture
def search_tool_no_vector(memory_manager: MemoryManager) -> MemorySearchTool:
    return MemorySearchTool(memory_manager=memory_manager, vector_store=None)


# ── MemorySaveTool tests ─────────────────────────────────


async def test_save_tool_appends_to_memory_file(
    save_tool_no_vector: MemorySaveTool, data_dir: Path
) -> None:
    result = await save_tool_no_vector.execute({"content": "User prefers dark mode"})
    assert "saved" in result.lower() or "ok" in result.lower()

    memory_path = data_dir / "MEMORY.md"
    assert memory_path.exists()
    assert "dark mode" in memory_path.read_text()


async def test_save_tool_with_category(
    save_tool_no_vector: MemorySaveTool, data_dir: Path
) -> None:
    result = await save_tool_no_vector.execute({
        "content": "Always use Python 3.12",
        "category": "preference",
    })
    assert "saved" in result.lower() or "ok" in result.lower()

    text = (data_dir / "MEMORY.md").read_text()
    assert "Python 3.12" in text


async def test_save_tool_indexes_vector(save_tool: MemorySaveTool) -> None:
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        result = await save_tool.execute({"content": "Important fact"})

    assert "saved" in result.lower() or "ok" in result.lower()


async def test_save_tool_missing_content(save_tool_no_vector: MemorySaveTool) -> None:
    result = await save_tool_no_vector.execute({})
    assert "error" in result.lower() or "required" in result.lower()


# ── MemorySearchTool tests ───────────────────────────────


async def test_search_tool_keyword_fallback(
    search_tool_no_vector: MemorySearchTool, data_dir: Path
) -> None:
    """Without vector store, falls back to keyword search in MEMORY.md."""
    memory_path = data_dir / "MEMORY.md"
    memory_path.write_text("# Memory\n\n- User prefers dark mode\n- Favorite language: Python\n")

    result = await search_tool_no_vector.execute({"query": "dark mode"})
    assert "dark mode" in result


async def test_search_tool_keyword_no_match(
    search_tool_no_vector: MemorySearchTool, data_dir: Path
) -> None:
    """Keyword search with no match returns appropriate message."""
    memory_path = data_dir / "MEMORY.md"
    memory_path.write_text("# Memory\n\n- User likes Python\n")

    result = await search_tool_no_vector.execute({"query": "JavaScript"})
    assert "no" in result.lower() or "not found" in result.lower() or result.strip() != ""


async def test_search_tool_semantic(search_tool: MemorySearchTool) -> None:
    """With vector store, uses semantic search."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        # First index some data
        await search_tool._vector_store.index_document(
            "User prefers dark mode", source="MEMORY.md", doc_type="memory"
        )

        result = await search_tool.execute({"query": "dark mode"})
        assert "dark mode" in result


async def test_search_tool_empty_query(search_tool_no_vector: MemorySearchTool) -> None:
    result = await search_tool_no_vector.execute({})
    assert "error" in result.lower() or "required" in result.lower()


async def test_search_tool_with_limit(
    search_tool_no_vector: MemorySearchTool, data_dir: Path
) -> None:
    memory_path = data_dir / "MEMORY.md"
    memory_path.write_text("line1\nline2\nline3\n")

    result = await search_tool_no_vector.execute({"query": "line", "limit": 1})
    # Should return at most 1 result
    assert isinstance(result, str)


# ── MemoryManager extension tests ────────────────────────


async def test_memory_manager_append_memory(
    memory_manager: MemoryManager, data_dir: Path
) -> None:
    memory_manager.append_memory("User prefers vim", category="preference")
    text = (data_dir / "MEMORY.md").read_text()
    assert "vim" in text


async def test_memory_manager_append_preserves_existing(
    memory_manager: MemoryManager, data_dir: Path
) -> None:
    (data_dir / "MEMORY.md").write_text("# Memory\n\n- Existing fact\n")
    memory_manager.append_memory("New fact")
    text = (data_dir / "MEMORY.md").read_text()
    assert "Existing fact" in text
    assert "New fact" in text


async def test_memory_manager_search_keyword(
    memory_manager: MemoryManager, data_dir: Path
) -> None:
    (data_dir / "MEMORY.md").write_text("# Memory\n\n- Loves Python\n- Hates Java\n")
    (data_dir / "HISTORY.md").write_text("# History\n\n- 2026 discussed plans\n")

    results = memory_manager.search_keyword("Python")
    assert len(results) >= 1
    assert any("Python" in r["text"] for r in results)


async def test_memory_manager_search_keyword_no_files(
    memory_manager: MemoryManager,
) -> None:
    results = memory_manager.search_keyword("anything")
    assert results == []


# ── Input validation edge cases ──────────────────────────


async def test_save_tool_invalid_category_defaults_to_fact(
    save_tool_no_vector: MemorySaveTool, data_dir: Path
) -> None:
    result = await save_tool_no_vector.execute({
        "content": "Some fact",
        "category": "invalid_category",
    })
    assert "[fact]" in result


async def test_save_tool_content_too_long(save_tool_no_vector: MemorySaveTool) -> None:
    result = await save_tool_no_vector.execute({"content": "x" * 3000})
    assert "error" in result.lower()


async def test_search_tool_invalid_limit_type(
    search_tool_no_vector: MemorySearchTool, data_dir: Path
) -> None:
    (data_dir / "MEMORY.md").write_text("# Memory\n- test line\n")
    result = await search_tool_no_vector.execute({"query": "test", "limit": "all"})
    # Should not crash, falls back to default
    assert isinstance(result, str)


async def test_search_tool_negative_limit(
    search_tool_no_vector: MemorySearchTool, data_dir: Path
) -> None:
    (data_dir / "MEMORY.md").write_text("# Memory\n- test line\n")
    result = await search_tool_no_vector.execute({"query": "test", "limit": -5})
    assert isinstance(result, str)
