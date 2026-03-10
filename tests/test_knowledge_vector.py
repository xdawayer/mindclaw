# input: knowledge/vector.py, config/schema.py
# output: VectorStore 测试
# pos: 向量搜索模块单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for VectorStore — LanceDB vector search with embedding and chunking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.config.schema import VectorDbConfig
from mindclaw.knowledge.vector import SearchResult, VectorStore

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def vector_config() -> VectorDbConfig:
    return VectorDbConfig(enabled=True, chunk_size=50, chunk_overlap=10, top_k=3)


@pytest.fixture
def disabled_config() -> VectorDbConfig:
    return VectorDbConfig(enabled=False)


@pytest.fixture
def mock_router() -> MagicMock:
    return MagicMock()


@pytest.fixture
def store(tmp_path: Path, vector_config: VectorDbConfig, mock_router: MagicMock) -> VectorStore:
    return VectorStore(data_dir=tmp_path, config=vector_config, router=mock_router)


@pytest.fixture
def disabled_store(
    tmp_path: Path, disabled_config: VectorDbConfig, mock_router: MagicMock
) -> VectorStore:
    return VectorStore(data_dir=tmp_path, config=disabled_config, router=mock_router)


# ── Disabled mode tests ──────────────────────────────────


async def test_disabled_store_search_returns_empty(disabled_store: VectorStore) -> None:
    results = await disabled_store.search("anything")
    assert results == []


async def test_disabled_store_index_is_noop(disabled_store: VectorStore) -> None:
    count = await disabled_store.index_document("some text", source="test", doc_type="memory")
    assert count == 0


async def test_disabled_store_remove_is_noop(disabled_store: VectorStore) -> None:
    count = await disabled_store.remove_by_source("test")
    assert count == 0


async def test_disabled_store_count_is_zero(disabled_store: VectorStore) -> None:
    assert await disabled_store.count() == 0


# ── Chunking tests ───────────────────────────────────────


def test_chunk_text_basic(store: VectorStore) -> None:
    text = "A" * 120  # 120 chars, chunk_size=50, overlap=10
    chunks = store._chunk_text(text, source="test.md")
    # Expected: ceil((120 - 10) / (50 - 10)) + 1 = ceil(110/40) + ? => 3 chunks
    assert len(chunks) >= 2
    for i, chunk in enumerate(chunks):
        assert chunk["source"] == "test.md"
        assert chunk["chunk_idx"] == i
        assert len(chunk["text"]) <= 50


def test_chunk_text_short(store: VectorStore) -> None:
    """Text shorter than chunk_size returns single chunk."""
    chunks = store._chunk_text("Hello world", source="s")
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Hello world"
    assert chunks[0]["chunk_idx"] == 0


def test_chunk_text_empty(store: VectorStore) -> None:
    chunks = store._chunk_text("", source="s")
    assert chunks == []


# ── Embedding tests ──────────────────────────────────────


async def test_get_embedding_calls_litellm(store: VectorStore) -> None:
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        result = await store._get_embedding("test text")

    assert result == [0.1] * 1536
    mock_embed.assert_called_once()


async def test_get_embedding_uses_configured_model(store: VectorStore) -> None:
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0] * 1536)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        await store._get_embedding("test")

    call_kwargs = mock_embed.call_args
    assert call_kwargs.kwargs["model"] == "text-embedding-3-small"


# ── Index & Search integration tests (with mocked embedding) ─


async def test_index_and_search(store: VectorStore) -> None:
    """Index a document and search for it."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        count = await store.index_document(
            "The user prefers Python over JavaScript",
            source="MEMORY.md",
            doc_type="memory",
        )
        assert count >= 1

        results = await store.search("Python preference")
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)
        assert results[0].source == "MEMORY.md"
        assert results[0].doc_type == "memory"
        assert "Python" in results[0].text


async def test_search_with_doc_type_filter(store: VectorStore) -> None:
    """Search filtered by doc_type returns only matching documents."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        await store.index_document("fact A", source="MEMORY.md", doc_type="memory")
        await store.index_document("fact B", source="HISTORY.md", doc_type="history")

        results = await store.search("fact", doc_type="memory")
        for r in results:
            assert r.doc_type == "memory"


async def test_remove_by_source(store: VectorStore) -> None:
    """After removing by source, search should not find those documents."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        await store.index_document("some data", source="old_source", doc_type="memory")
        assert await store.count() >= 1

        removed = await store.remove_by_source("old_source")
        assert removed >= 1

        results = await store.search("some data")
        sources = [r.source for r in results]
        assert "old_source" not in sources


async def test_index_memory_convenience(store: VectorStore) -> None:
    """index_memory should index with source=MEMORY.md and doc_type=memory."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        count = await store.index_memory("User prefers dark mode")
        assert count >= 1


async def test_index_history_convenience(store: VectorStore) -> None:
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        count = await store.index_history("2026-03-10 discussed project plan")
        assert count >= 1


async def test_count(store: VectorStore) -> None:
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response

        assert await store.count() == 0
        await store.index_document("data", source="s", doc_type="test")
        assert await store.count() >= 1


# ── Graceful degradation ─────────────────────────────────


async def test_embedding_failure_returns_empty_search(store: VectorStore) -> None:
    """If embedding API fails, search returns empty list instead of crashing."""
    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.side_effect = RuntimeError("API error")
        results = await store.search("anything")
        assert results == []


async def test_embedding_failure_index_returns_zero(store: VectorStore) -> None:
    """If embedding API fails during indexing, return 0 and don't crash."""
    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.side_effect = RuntimeError("API error")
        count = await store.index_document("text", source="s", doc_type="t")
        assert count == 0


# ── Injection prevention ─────────────────────────────────


async def test_remove_by_source_with_special_chars(store: VectorStore) -> None:
    """Source with SQL injection chars should not crash."""
    removed = await store.remove_by_source("test'; DROP TABLE documents; --")
    assert removed == 0


async def test_search_with_special_doc_type(store: VectorStore) -> None:
    """doc_type with injection chars should not crash."""
    fake_embedding = [0.1] * 1536
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=fake_embedding)]

    with patch("mindclaw.knowledge.vector.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_response
        results = await store.search("test", doc_type="'; DROP TABLE docs; --")
        assert results == []


# ── Public enabled property ──────────────────────────────


def test_enabled_property(store: VectorStore) -> None:
    assert store.enabled is True


def test_disabled_enabled_property(disabled_store: VectorStore) -> None:
    assert disabled_store.enabled is False
