# input: config/schema.py, litellm (aembedding)
# output: 导出 VectorStore, SearchResult
# pos: 知识层向量搜索，LanceDB 本地向量数据库 + embedding
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""LanceDB-based vector store for semantic search in MindClaw.

Provides document indexing with chunking and embedding, plus similarity search.
Gracefully degrades when LanceDB is not installed or embedding API is unavailable.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from mindclaw.config.schema import VectorDbConfig

try:
    import lancedb
    import pyarrow as pa

    _HAS_LANCEDB = True
except ImportError:
    _HAS_LANCEDB = False

try:
    from litellm import aembedding
except ImportError:
    aembedding = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SearchResult:
    """A single semantic search result."""

    text: str
    source: str
    doc_type: str
    score: float


def _get_schema(dimensions: int) -> pa.Schema:
    """Build PyArrow schema for the LanceDB table."""
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("text", pa.string()),
            pa.field("source", pa.string()),
            pa.field("doc_type", pa.string()),
            pa.field("chunk_idx", pa.int32()),
            pa.field("created_at", pa.float64()),
            pa.field("vector", pa.list_(pa.float32(), dimensions)),
        ]
    )


def _escape_filter_value(value: str) -> str:
    """Escape single quotes in filter values to prevent SQL-like injection."""
    return value.replace("'", "''")


class VectorStore:
    """LanceDB-powered vector store with embedding via LiteLLM.

    When config.enabled is False, all methods are no-ops (Null Object pattern).
    When lancedb is not installed, behaves identically to disabled mode.
    """

    def __init__(
        self,
        data_dir: Path,
        config: VectorDbConfig,
        router: Any = None,
    ) -> None:
        self._config = config
        self._router = router
        self._enabled = config.enabled and _HAS_LANCEDB
        self._db: Any = None
        self._table: Any = None

        if self._enabled:
            db_path = data_dir / config.db_path
            db_path.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(db_path))
            self._ensure_table()

    @property
    def enabled(self) -> bool:
        """Whether the vector store is active."""
        return self._enabled

    # ── Table management ─────────────────────────────────

    def _ensure_table(self) -> None:
        """Create or open the LanceDB table."""
        table_name = self._config.table_name
        schema = _get_schema(self._config.embedding_dimensions)
        if table_name in self._db.list_tables():
            self._table = self._db.open_table(table_name)
        else:
            self._table = self._db.create_table(table_name, schema=schema)

    # ── Embedding ────────────────────────────────────────

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector via LiteLLM aembedding."""
        if aembedding is None:
            raise RuntimeError("litellm is required for embedding")

        kwargs: dict[str, Any] = {
            "model": self._config.embedding_model,
            "input": [text],
        }

        # Pass provider API key if available
        if self._router is not None and hasattr(self._router, "config"):
            model = self._config.embedding_model
            provider = model.split("/")[0] if "/" in model else "openai"
            settings = self._router.config.providers.get(provider)
            if settings and settings.api_key:
                kwargs["api_key"] = settings.api_key

        response = await aembedding(**kwargs)
        return response.data[0].embedding

    # ── Chunking ─────────────────────────────────────────

    def _chunk_text(self, text: str, source: str) -> list[dict]:
        """Split text into overlapping chunks."""
        if not text:
            return []

        chunk_size = self._config.chunk_size
        overlap = self._config.chunk_overlap
        step = max(chunk_size - overlap, 1)

        chunks: list[dict] = []
        idx = 0
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            chunks.append({"text": chunk_text, "source": source, "chunk_idx": idx})
            idx += 1
            start += step
            if end == len(text):
                break

        return chunks

    # ── Index operations ─────────────────────────────────

    async def index_document(
        self,
        text: str,
        source: str,
        doc_type: str,
    ) -> int:
        """Index a document (with chunking + embedding). Returns chunk count."""
        if not self._enabled:
            return 0

        chunks = self._chunk_text(text, source)
        if not chunks:
            return 0

        try:
            rows: list[dict] = []
            for chunk in chunks:
                embedding = await self._get_embedding(chunk["text"])
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": chunk["text"],
                        "source": source,
                        "doc_type": doc_type,
                        "chunk_idx": chunk["chunk_idx"],
                        "created_at": time.time(),
                        "vector": embedding,
                    }
                )

            self._table.add(rows)
            logger.debug(f"Indexed {len(rows)} chunks from {source} ({doc_type})")
            return len(rows)

        except Exception:
            logger.exception(f"Failed to index document from {source}")
            return 0

    async def index_memory(self, memory_text: str) -> int:
        """Index MEMORY.md content (removes old entries first)."""
        if not self._enabled:
            return 0
        await self.remove_by_source("MEMORY.md")
        return await self.index_document(memory_text, source="MEMORY.md", doc_type="memory")

    async def index_history(self, history_text: str) -> int:
        """Index HISTORY.md content (removes old entries first)."""
        if not self._enabled:
            return 0
        await self.remove_by_source("HISTORY.md")
        return await self.index_document(history_text, source="HISTORY.md", doc_type="history")

    async def remove_by_source(self, source: str) -> int:
        """Remove all documents with the given source. Returns removed count."""
        if not self._enabled:
            return 0

        try:
            before = await self.count()
            safe_source = _escape_filter_value(source)
            self._table.delete(f"source = '{safe_source}'")
            after = await self.count()
            removed = before - after
            if removed > 0:
                logger.debug(f"Removed {removed} chunks from source={source}")
            return removed
        except Exception:
            logger.exception(f"Failed to remove documents for source={source}")
            return 0

    # ── Search ───────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        doc_type: str | None = None,
    ) -> list[SearchResult]:
        """Semantic search. Returns top-k most similar chunks."""
        if not self._enabled:
            return []

        k = top_k or self._config.top_k

        try:
            embedding = await self._get_embedding(query)
            q = self._table.search(embedding).limit(k)

            if doc_type is not None:
                safe_doc_type = _escape_filter_value(doc_type)
                q = q.where(f"doc_type = '{safe_doc_type}'")

            raw_results = q.to_list()

            return [
                SearchResult(
                    text=row["text"],
                    source=row["source"],
                    doc_type=row["doc_type"],
                    score=max(0.0, 1.0 - row.get("_distance", 0.0)),
                )
                for row in raw_results
            ]

        except Exception:
            logger.exception("Vector search failed")
            return []

    # ── Utilities ────────────────────────────────────────

    async def count(self) -> int:
        """Return the number of indexed chunks."""
        if not self._enabled:
            return 0
        try:
            return self._table.count_rows()
        except Exception:
            return 0
