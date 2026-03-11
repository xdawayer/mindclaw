# input: knowledge/memory.py, knowledge/vector.py, skills/registry.py,
#        orchestrator/cron_context.py
# output: 导出 ContextBuilder
# pos: 动态构建系统提示，注入记忆、日期、技能和语义搜索结果 (含 cron 专用提示)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Dynamic system prompt builder with memory, skill, and vector search injection."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from loguru import logger

from mindclaw.knowledge.memory import MemoryManager
from mindclaw.orchestrator.cron_context import CronExecutionConstraints

if TYPE_CHECKING:
    from mindclaw.knowledge.vector import VectorStore
    from mindclaw.skills.registry import SkillRegistry

_BASE_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message."""


class ContextBuilder:
    """Build the system prompt dynamically, injecting memory, date, skills, and vector context."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        skill_registry: SkillRegistry | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._skill_registry = skill_registry
        self._vector_store = vector_store

    def build_system_prompt(self, user_message: str | None = None) -> str:
        """Assemble the full system prompt (sync version, no vector search)."""
        return self._build_base_prompt()

    async def abuild_system_prompt(self, user_message: str | None = None) -> str:
        """Assemble the full system prompt with optional vector search injection."""
        parts_base = self._build_base_prompt()

        # Semantic memory injection (only if vector store + user message)
        if self._vector_store and user_message:
            try:
                results = await self._vector_store.search(user_message, top_k=3)
                if results:
                    lines = [f"- [{r.source}] {r.text}" for r in results]
                    parts_base += (
                        "\n\n## Relevant Context (from semantic search)\n"
                        + "\n".join(lines)
                    )
            except Exception:
                logger.warning("Vector search failed during context building")

        return parts_base

    def build_cron_system_prompt(
        self, constraints: CronExecutionConstraints,
    ) -> str:
        """Build a system prompt for unattended cron/scheduled task execution."""
        base = self._build_base_prompt()

        blocked = ", ".join(sorted(constraints.blocked_tools)) or "none"
        cron_section = (
            "\n\n## Scheduled Task Execution\n"
            "You are running as an unattended scheduled task. "
            "Follow these constraints strictly:\n"
            f"- Max iterations: {constraints.max_iterations}\n"
            f"- Timeout: {constraints.timeout_seconds} seconds\n"
            f"- Blocked tools (do NOT call): {blocked}\n"
            "- Complete the task efficiently within these limits.\n"
            "- Do not ask follow-up questions; the user is not present."
        )

        return base + cron_section

    def _build_base_prompt(self) -> str:
        """Build the base prompt with date, memory, and skills."""
        parts: list[str] = [_BASE_PROMPT]

        # Current date section
        parts.append(f"\n## Current Date\n{date.today().isoformat()}")

        # Memory section (only if content exists)
        memory = self._memory_manager.load_memory()
        if memory:
            parts.append(f"\n## Memory (what you know about the user)\n{memory}")

        # Skills section (only if registry is provided and has skills)
        if self._skill_registry:
            summaries = self._skill_registry.get_skill_summaries()
            if summaries:
                parts.append(
                    "\n## Available Skills\n"
                    "Use read_file to load a skill's full content when needed.\n"
                    + "\n".join(summaries)
                )

            always_content = self._skill_registry.get_always_skills_content()
            if always_content:
                parts.append(f"\n## Active Skills\n{always_content}")

        return "\n".join(parts)
