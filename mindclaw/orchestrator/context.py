# input: knowledge/memory.py
# output: 导出 ContextBuilder
# pos: 动态构建系统提示，注入记忆和日期
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Dynamic system prompt builder with memory injection."""

from __future__ import annotations

from datetime import date

from mindclaw.knowledge.memory import MemoryManager

_BASE_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message."""


class ContextBuilder:
    """Build the system prompt dynamically, injecting memory and current date."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    def build_system_prompt(self) -> str:
        """Assemble the full system prompt with date and optional memory."""
        parts: list[str] = [_BASE_PROMPT]

        # Current date section
        parts.append(f"\n## Current Date\n{date.today().isoformat()}")

        # Memory section (only if content exists)
        memory = self._memory_manager.load_memory()
        if memory:
            parts.append(f"\n## Memory (what you know about the user)\n{memory}")

        return "\n".join(parts)
