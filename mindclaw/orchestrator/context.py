# input: knowledge/memory.py, skills/registry.py
# output: 导出 ContextBuilder
# pos: 动态构建系统提示，注入记忆、日期和技能
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Dynamic system prompt builder with memory and skill injection."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from mindclaw.knowledge.memory import MemoryManager

if TYPE_CHECKING:
    from mindclaw.skills.registry import SkillRegistry

_BASE_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message."""


class ContextBuilder:
    """Build the system prompt dynamically, injecting memory, date, and skills."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._memory_manager = memory_manager
        self._skill_registry = skill_registry

    def build_system_prompt(self) -> str:
        """Assemble the full system prompt with date, memory, and skills."""
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
