# input: knowledge/session.py, llm/router.py, config/schema.py
# output: 导出 MemoryManager
# pos: LLM 驱动的记忆整合，管理 MEMORY.md 和 HISTORY.md，含 append_memory + search_keyword
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""LLM-driven memory consolidation for MindClaw.

Uses the LLM to extract important facts from conversation history and merge
them into persistent MEMORY.md and HISTORY.md files.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter

_CONSOLIDATION_PROMPT = """\
You are a memory manager for MindClaw, a personal AI assistant.

Your task: Extract important information from the conversation below
and merge it with existing memory.

## Existing Memory
{existing_memory}

## Conversation to Process
{conversation}

## Instructions
1. Extract facts worth remembering long-term: user preferences, key facts, important decisions.
2. Merge with existing memory: keep what's still relevant, remove outdated, add new.
3. Output the complete updated memory in this exact Markdown format:

# MindClaw Memory

## 用户偏好
- (user preferences, habits, communication style)

## 关键事实
- (key facts about the user, their projects, environment)

## 重要决定
- (important decisions, architectural choices, agreements)

Only output the Markdown content. No explanation or commentary.
"""


class MemoryManager:
    """Consolidate conversation history into MEMORY.md and HISTORY.md via LLM."""

    def __init__(
        self,
        data_dir: Path,
        router: LLMRouter,
        config: MindClawConfig,
        vector_store: Any | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._router = router
        self._config = config
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def consolidate(
        self, session_key: str, session_store: SessionStore
    ) -> bool:
        """Execute consolidation. Returns True if successful."""
        keep_recent = self._config.knowledge.consolidation_keep_recent

        # 1. Get messages to consolidate
        to_consolidate = session_store.load_for_consolidation(
            session_key, keep_recent=keep_recent
        )
        if not to_consolidate:
            return False

        # 2. Read existing memory
        existing_memory = self.load_memory()

        # 3. Build prompt
        conversation_text = "\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in to_consolidate
        )
        prompt = _CONSOLIDATION_PROMPT.format(
            existing_memory=existing_memory or "(none)",
            conversation=conversation_text,
        )

        # 4. Call LLM
        try:
            result = await self._router.chat(
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception:
            logger.exception("Memory consolidation LLM call failed")
            return False

        new_memory = result.content or ""

        # 5. Write MEMORY.md
        memory_path = self._data_dir / "MEMORY.md"
        memory_path.write_text(new_memory, encoding="utf-8")

        # 6. Append to HISTORY.md
        self._append_history(session_key, len(to_consolidate))

        # 7. Mark consolidated — compute new pointer
        all_messages, _current_pointer = session_store._read_lines(session_key)
        new_pointer = len(all_messages) - keep_recent
        session_store.mark_consolidated(session_key, pointer=new_pointer)

        # 8. Index in vector store if available
        if self._vector_store is not None:
            try:
                await self._vector_store.index_memory(new_memory)
                history_path = self._data_dir / "HISTORY.md"
                if history_path.exists():
                    history_text = history_path.read_text(encoding="utf-8")
                    await self._vector_store.index_history(history_text)
            except Exception:
                logger.warning("Vector indexing after consolidation failed")

        logger.info(
            f"Consolidated {len(to_consolidate)} messages for {session_key}"
        )
        return True

    def should_consolidate(self, unconsolidated_count: int) -> bool:
        """Check if auto-consolidation should trigger (> threshold)."""
        return unconsolidated_count > self._config.knowledge.consolidation_threshold

    def load_memory(self) -> str:
        """Read MEMORY.md content. Returns empty string if not found."""
        memory_path = self._data_dir / "MEMORY.md"
        if not memory_path.exists():
            return ""
        return memory_path.read_text(encoding="utf-8")

    def append_memory(self, content: str, category: str = "fact") -> None:
        """Append a single memory entry to MEMORY.md (direct file op, no LLM)."""
        memory_path = self._data_dir / "MEMORY.md"

        if not memory_path.exists() or memory_path.stat().st_size == 0:
            header = "# MindClaw Memory\n\n"
        else:
            header = ""

        category_label = {
            "preference": "用户偏好",
            "fact": "关键事实",
            "decision": "重要决定",
        }.get(category, "关键事实")

        entry = f"- [{category_label}] {content}\n"

        with memory_path.open("a", encoding="utf-8") as fh:
            fh.write(header + entry)

    def search_keyword(self, query: str) -> list[dict]:
        """Keyword search across MEMORY.md and HISTORY.md. Returns matching lines."""
        results: list[dict] = []
        query_lower = query.lower()

        for filename in ("MEMORY.md", "HISTORY.md"):
            filepath = self._data_dir / filename
            if not filepath.exists():
                continue
            for line in filepath.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and query_lower in stripped.lower():
                    results.append({"source": filename, "text": stripped})

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_history(self, session_key: str, message_count: int) -> None:
        """Append a consolidation entry to HISTORY.md."""
        history_path = self._data_dir / "HISTORY.md"

        if not history_path.exists() or history_path.stat().st_size == 0:
            header = "# MindClaw History\n\n"
        else:
            header = ""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] 整合了 {message_count} 条消息 (session: {session_key})\n"

        with history_path.open("a", encoding="utf-8") as fh:
            fh.write(header + entry)
