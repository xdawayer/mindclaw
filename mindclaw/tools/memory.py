# input: tools/base.py, knowledge/memory.py, knowledge/vector.py
# output: 导出 MemorySaveTool, MemorySearchTool
# pos: 记忆工具 — LLM 可调用的记忆保存和语义/关键词搜索
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Memory tools: save facts to long-term memory and search by semantic or keyword."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from mindclaw.tools.base import RiskLevel, Tool

if TYPE_CHECKING:
    from mindclaw.knowledge.memory import MemoryManager
    from mindclaw.knowledge.vector import VectorStore

_VALID_CATEGORIES = {"preference", "fact", "decision"}
_MAX_CONTENT_LENGTH = 2000
_MAX_LIMIT = 50


class MemorySaveTool(Tool):
    """Save an important fact or preference to long-term memory."""

    name = "memory_save"
    description = (
        "Save an important fact, preference, or decision to long-term memory. "
        "Use this when the user shares something worth remembering across sessions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The fact or preference to remember.",
            },
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "decision"],
                "description": "Category of the memory (optional).",
            },
        },
        "required": ["content"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(
        self,
        memory_manager: MemoryManager,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._vector_store = vector_store

    async def execute(self, params: dict) -> str:
        content = params.get("content", "").strip()
        if not content:
            return "Error: 'content' is required."
        if len(content) > _MAX_CONTENT_LENGTH:
            return f"Error: content exceeds maximum length ({_MAX_CONTENT_LENGTH} chars)."

        category = params.get("category", "fact")
        if category not in _VALID_CATEGORIES:
            category = "fact"

        # 1. Append to MEMORY.md
        self._memory_manager.append_memory(content, category=category)

        # 2. Index in vector store if available
        if self._vector_store is not None:
            try:
                await self._vector_store.index_document(
                    content, source="MEMORY.md", doc_type="memory"
                )
            except Exception:
                logger.warning("Failed to index memory in vector store")

        return f"Saved to memory [{category}]: {content}"


class MemorySearchTool(Tool):
    """Search long-term memory using semantic or keyword search."""

    name = "memory_search"
    description = (
        "Search long-term memory and history. Uses semantic search if vector DB "
        "is enabled, otherwise falls back to keyword search in MEMORY.md and HISTORY.md."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of results (default 5).",
            },
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(
        self,
        memory_manager: MemoryManager,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._vector_store = vector_store

    async def execute(self, params: dict) -> str:
        query = params.get("query", "").strip()
        if not query:
            return "Error: 'query' is required."

        try:
            limit = max(1, min(int(params.get("limit", 5)), _MAX_LIMIT))
        except (TypeError, ValueError):
            limit = 5

        # Semantic search if vector store is available and enabled
        if self._vector_store is not None and self._vector_store.enabled:
            try:
                results = await self._vector_store.search(query, top_k=limit)
                if results:
                    lines = [
                        f"- [{r.source}] (score: {r.score:.2f}) {r.text}"
                        for r in results
                    ]
                    return f"Found {len(results)} results:\n" + "\n".join(lines)
            except Exception:
                logger.warning("Semantic search failed, falling back to keyword search")

        # Keyword fallback
        matches = self._memory_manager.search_keyword(query)
        if not matches:
            return f"No results found for '{query}'."

        limited = matches[:limit]
        lines = [f"- [{m['source']}] {m['text']}" for m in limited]
        return f"Found {len(limited)} results:\n" + "\n".join(lines)
