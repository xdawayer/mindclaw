# input: tools/base.py, skills/installer.py, skills/registry.py, skills/index_client.py
# output: 导出 SkillSearchTool, SkillShowTool, SkillInstallTool, SkillRemoveTool, SkillListTool
# pos: LLM 可调用的技能管理工具集，对话中搜索/安装/删除技能
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""LLM-accessible tools for skill management: search, show, install, remove, list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from mindclaw.skills.integrity import sanitize_approval_text
from mindclaw.tools.base import RiskLevel, Tool

if TYPE_CHECKING:
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry


class SkillSearchTool(Tool):
    name = "skill_search"
    description = "Search the skill index for available skills to install"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (name, description, or tag)",
            },
        },
        "required": ["query"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, index_client: IndexClient | None) -> None:
        self._client = index_client

    async def execute(self, params: dict) -> str:
        if not self._client:
            return "Error: Skill index not configured."
        query = params["query"]
        results = await self._client.search(query)
        if not results:
            return f"No skills found matching '{query}'."
        lines = []
        for entry in results[:10]:
            verified = "[verified]" if entry.verified else "[unverified]"
            lines.append(
                f"- {entry.name}: {entry.description} {verified}\n"
                f"  Source: {entry.source} | Tags: {', '.join(entry.tags)}"
            )
        return f"Found {len(results)} skill(s):\n" + "\n".join(lines)


class SkillShowTool(Tool):
    name = "skill_show"
    description = "Show details and full content of an installed skill"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name to show"},
        },
        "required": ["name"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def execute(self, params: dict) -> str:
        name = params["name"]
        skill = self._registry.get(name)
        if not skill:
            return f"Skill '{name}' not found."
        return (
            f"Name: {skill.name}\n"
            f"Description: {skill.description}\n"
            f"Load: {skill.load}\n"
            f"Source: {skill.source_layer}\n"
            f"File: {skill.file_path}\n"
            f"---\n"
            f"{skill.content}"
        )


class SkillInstallTool(Tool):
    name = "skill_install"
    description = (
        "Install a skill from a source (local file, URL, github:user/repo@name, or index name). "
        "This is a DANGEROUS operation that requires user approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": (
                    "Skill source: local path, HTTPS URL, "
                    "github:user/repo@skill-name, or skill name from index"
                ),
            },
            "force": {
                "type": "boolean",
                "description": "Force overwrite if skill already exists (default: false)",
            },
        },
        "required": ["source"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, installer: SkillInstaller, registry: SkillRegistry) -> None:
        self._installer = installer
        self._registry = registry

    async def execute(self, params: dict) -> str:
        source = params["source"]
        force = params.get("force", False)

        result = await self._installer.install_from_source(source, force=force)

        if not result.success:
            return f"Installation failed: {result.error}"

        safe_name = sanitize_approval_text(result.name)
        safe_desc = sanitize_approval_text(result.description)
        logger.info(f"Skill '{safe_name}' installed via LLM tool from {source}")

        return (
            f"Skill '{safe_name}' installed successfully.\n"
            f"Description: {safe_desc}\n"
            f"SHA256: {result.sha256}\n"
            f"---\n"
            f"Full skill content (available for immediate use):\n\n"
            f"{result.content}"
        )


class SkillRemoveTool(Tool):
    name = "skill_remove"
    description = (
        "Remove a user-installed skill. Cannot remove built-in skills. "
        "This is a DANGEROUS operation that requires user approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the skill to remove"},
        },
        "required": ["name"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, installer: SkillInstaller) -> None:
        self._installer = installer

    async def execute(self, params: dict) -> str:
        name = params["name"]
        result = self._installer.remove(name)
        if not result.success:
            return f"Remove failed: {result.error}"
        return f"Skill '{name}' removed successfully."


class SkillListTool(Tool):
    name = "skill_list"
    description = "List all available skills with their source layer (builtin/project/user)"
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.SAFE

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    async def execute(self, params: dict) -> str:
        skills = self._registry.skills
        if not skills:
            return "No skills installed."
        lines = []
        for s in sorted(skills, key=lambda x: x.name):
            lines.append(
                f"- {s.name}: {s.description} [{s.source_layer}] (load: {s.load})"
            )
        return f"{len(skills)} skill(s):\n" + "\n".join(lines)
