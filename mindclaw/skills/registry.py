# input: pathlib, re (YAML front-matter parsing)
# output: 导出 SkillRegistry, SkillMetadata
# pos: 技能注册中心，扫描多个 skills/ 目录解析 YAML front-matter，后层覆盖前层
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill registry: discovers and indexes SKILL.md files from multiple directories."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from loguru import logger

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")

# Layer names indexed by directory position (builtin=0, project=1, user=2+).
_LAYER_NAMES = ("builtin", "project", "user")


@dataclass
class SkillMetadata:
    name: str
    description: str
    load: str  # "on_demand" | "always"
    file_path: Path
    content: str  # Full markdown content (after front-matter)
    source_layer: str = field(default="builtin")


class SkillRegistry:
    """Discover and index skill markdown files from one or more directories.

    Directories are scanned in order (builtin → project → user).  Later
    directories win on name collisions — a user-layer skill overrides a
    builtin-layer skill of the same name.  Skill names found in the *first*
    directory are stored as protected_names.
    """

    def __init__(self, skills_dir: Union[list[Path], Path]) -> None:
        # Normalise: accept a single Path for backward compatibility.
        if isinstance(skills_dir, Path):
            self._dirs: list[Path] = [skills_dir]
        else:
            self._dirs = list(skills_dir)

        self._skills: dict[str, SkillMetadata] = {}
        self._protected_names: frozenset[str] = frozenset()
        self._discover_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def skills(self) -> list[SkillMetadata]:
        return list(self._skills.values())

    @property
    def protected_names(self) -> frozenset[str]:
        """Skill names that originate from the first (builtin) directory."""
        return self._protected_names

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

    def reload(self) -> None:
        """Atomically rebuild the skills dict from disk.

        Builds a fresh dict first, then replaces self._skills in a single
        assignment — never mutates the existing dict in place.
        """
        new_skills, new_protected = self._build_skills_dict()
        self._skills = new_skills
        self._protected_names = new_protected

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_all(self) -> None:
        """Initial discovery — delegates to _build_skills_dict."""
        self._skills, self._protected_names = self._build_skills_dict()

    def _build_skills_dict(self) -> tuple[dict[str, SkillMetadata], frozenset[str]]:
        """Scan all directories and return (skills_dict, protected_names).

        Directories are processed in order; later directories override earlier
        ones on name collision.  The first directory's final skill names become
        protected_names.
        """
        skills: dict[str, SkillMetadata] = {}
        first_dir_names: frozenset[str] = frozenset()

        for idx, skills_dir in enumerate(self._dirs):
            layer_name = _LAYER_NAMES[idx] if idx < len(_LAYER_NAMES) else f"layer{idx}"
            self._discover_into(skills_dir, skills, layer_name)
            if idx == 0:
                first_dir_names = frozenset(skills.keys())

        return skills, first_dir_names

    def _discover_into(
        self,
        skills_dir: Path,
        target: dict[str, SkillMetadata],
        layer_name: str,
    ) -> None:
        """Glob *.md files in skills_dir and load them into target.

        Skips files whose name starts with '_'.
        Emits a warning when overriding an existing skill.
        """
        if not skills_dir.is_dir():
            logger.debug(f"Skills directory not found: {skills_dir}")
            return

        for path in sorted(skills_dir.glob("*.md")):
            if path.name.startswith("_"):
                logger.debug(f"Skipping underscore-prefixed file: {path.name}")
                continue
            meta = self._parse_skill(path, layer_name)
            if meta is None:
                continue
            if meta.name in target:
                logger.warning(
                    f"Skill '{meta.name}' from layer '{layer_name}' overrides "
                    f"layer '{target[meta.name].source_layer}' (file: {path})"
                )
            target[meta.name] = meta
            logger.debug(
                f"Discovered skill: {meta.name} "
                f"(load={meta.load}, layer={layer_name})"
            )

    def _parse_skill(self, path: Path, layer: str) -> SkillMetadata | None:
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
            source_layer=layer,
        )
