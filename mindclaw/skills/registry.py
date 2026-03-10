# input: pathlib, re (YAML front-matter parsing)
# output: 导出 SkillRegistry, SkillMetadata
# pos: 技能注册中心，扫描 skills/ 目录解析 YAML front-matter
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill registry: discovers and indexes SKILL.md files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")


@dataclass
class SkillMetadata:
    name: str
    description: str
    load: str  # "on_demand" | "always"
    file_path: Path
    content: str  # Full markdown content (after front-matter)


class SkillRegistry:
    """Discover and index skill markdown files from a directory."""

    def __init__(self, skills_dir: Path) -> None:
        self._skills: dict[str, SkillMetadata] = {}
        self._discover(skills_dir)

    @property
    def skills(self) -> list[SkillMetadata]:
        return list(self._skills.values())

    def get(self, name: str) -> SkillMetadata | None:
        return self._skills.get(name)

    def get_skill_summaries(self) -> list[str]:
        """Return name + description lines for system prompt injection."""
        return [
            f"- {s.name}: {s.description}"
            for s in self._skills.values()
        ]

    def get_always_skills_content(self) -> str:
        """Return full content of all 'always' load skills."""
        parts = [
            s.content
            for s in self._skills.values()
            if s.load == "always"
        ]
        return "\n".join(parts)

    def _discover(self, skills_dir: Path) -> None:
        if not skills_dir.is_dir():
            logger.debug(f"Skills directory not found: {skills_dir}")
            return

        for path in sorted(skills_dir.glob("*.md")):
            meta = self._parse_skill(path)
            if meta:
                self._skills[meta.name] = meta
                logger.debug(f"Discovered skill: {meta.name} (load={meta.load})")

    def _parse_skill(self, path: Path) -> SkillMetadata | None:
        """Parse a skill file, extracting YAML front-matter metadata."""
        text = path.read_text(encoding="utf-8")

        match = _FRONT_MATTER_RE.match(text)
        if not match:
            logger.debug(f"Skipping {path.name}: no valid YAML front-matter")
            return None

        front_matter = match.group(1)
        content = text[match.end():]

        fields: dict[str, str] = {}
        for line in front_matter.strip().splitlines():
            line_match = _YAML_LINE_RE.match(line.strip())
            if line_match:
                fields[line_match.group(1)] = line_match.group(2).strip()

        name = fields.get("name")
        description = fields.get("description", "")
        load = fields.get("load", "on_demand")

        if not name:
            logger.debug(f"Skipping {path.name}: missing 'name' in front-matter")
            return None

        return SkillMetadata(
            name=name,
            description=description,
            load=load,
            file_path=path,
            content=content.strip(),
        )
