# input: mindclaw.skills.registry, mindclaw.skills.integrity, httpx, pathlib, re
# output: 导出 InstallResult, SkillInstaller
# pos: 技能安装器，处理本地/URL/GitHub/索引来源的下载、验证、安装、删除、更新
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill installer: download, validate, install, remove, and update skills."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from mindclaw.skills.integrity import (
    compute_sha256,
    is_safe_download_url,
    validate_skill_content,
    validate_skill_size,
)

if TYPE_CHECKING:
    from mindclaw.skills.index_client import IndexClient
    from mindclaw.skills.registry import SkillRegistry

_GITHUB_RE = re.compile(r"^github:([^/]+)/([^@]+)@(.+)$")
_RAW_GITHUB_TEMPLATE = (
    "https://raw.githubusercontent.com/{user}/{repo}/{ref}/skills/{name}.md"
)
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FETCH_TIMEOUT = 30.0


@dataclass(frozen=True)
class InstallResult:
    """Result of an install or remove operation."""

    success: bool
    name: str = ""
    description: str = ""
    sha256: str = ""
    content: str = ""
    error: str = ""


class SkillInstaller:
    """Install, remove, and update skills.

    Validates size + format + SSRF + SHA256 before writing to disk.
    Only writes to user_skills_dir; never mutates builtin or project layers.
    """

    def __init__(
        self,
        user_skills_dir: Path,
        registry: "SkillRegistry",
        index_client: "IndexClient | None",
        max_skill_size: int = 8192,
    ) -> None:
        self._user_dir = user_skills_dir
        self._registry = registry
        self._index_client = index_client
        self._max_skill_size = max_skill_size

    # ------------------------------------------------------------------
    # Public install entry points
    # ------------------------------------------------------------------

    async def install_from_local(self, path: Path, force: bool = False) -> InstallResult:
        """Read a local .md file and install it."""
        try:
            content_bytes = path.read_bytes()
        except OSError as exc:
            return InstallResult(success=False, error=f"Cannot read file: {exc}")
        return await self.install_from_bytes(
            content_bytes=content_bytes,
            source=str(path),
            is_remote=False,
            force=force,
        )

    async def install_from_url(self, url: str, force: bool = False) -> InstallResult:
        """Download a skill from a URL and install it.

        Rejects non-HTTPS or private/loopback URLs via SSRF check.
        """
        if not is_safe_download_url(url):
            return InstallResult(
                success=False,
                error=f"Unsafe or non-HTTPS URL rejected: {url}",
            )
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()
                content_bytes = response.content
        except httpx.HTTPError as exc:
            return InstallResult(success=False, error=f"HTTP error downloading skill: {exc}")
        except OSError as exc:
            return InstallResult(success=False, error=f"Network error: {exc}")

        return await self.install_from_bytes(
            content_bytes=content_bytes,
            source=url,
            is_remote=True,
            force=force,
        )

    async def install_from_github(self, source: str, force: bool = False) -> InstallResult:
        """Parse github:user/repo@ref source and resolve to raw URL.

        Format: ``github:user/repo@commit_ref``
        The skill file is expected at: skills/{skill_name}.md in the repo.
        The skill name is extracted from the source after '@'.
        """
        match = _GITHUB_RE.match(source)
        if not match:
            return InstallResult(
                success=False,
                error=(
                    f"Invalid GitHub source '{source}'. "
                    "Expected format: github:user/repo@skill_name"
                ),
            )
        user, repo, ref = match.group(1), match.group(2), match.group(3)
        raw_url = _RAW_GITHUB_TEMPLATE.format(user=user, repo=repo, ref=ref, name=ref)
        logger.debug(f"Resolved GitHub source '{source}' → {raw_url}")
        return await self.install_from_url(raw_url, force=force)

    async def install_by_name(self, name: str, force: bool = False) -> InstallResult:
        """Lookup name in the skill index and install from its source URL."""
        if self._index_client is None:
            return InstallResult(
                success=False,
                error="No index client configured; cannot install by name",
            )
        entry = await self._index_client.resolve(name)
        if entry is None:
            return InstallResult(
                success=False,
                error=f"Skill '{name}' not found in the skill index",
            )
        return await self.install_from_source(entry.source, force=force)

    async def install_from_source(self, source: str, force: bool = False) -> InstallResult:
        """Route to the appropriate installer based on source type."""
        if source.startswith("github:"):
            return await self.install_from_github(source, force=force)
        if source.startswith("https://") or source.startswith("http://"):
            return await self.install_from_url(source, force=force)
        return await self.install_from_local(Path(source), force=force)

    # ------------------------------------------------------------------
    # Core install logic
    # ------------------------------------------------------------------

    async def install_from_bytes(
        self,
        content_bytes: bytes,
        source: str,
        is_remote: bool,
        force: bool,
        expected_sha256: str = "",
    ) -> InstallResult:
        """Core install logic: validate, check constraints, write to disk."""
        error = self._validate_content(content_bytes, expected_sha256)
        if error is not None:
            return error

        content_str = content_bytes.decode("utf-8", errors="replace")
        validation = validate_skill_content(content_str)
        name = validation.name
        description = validation.description
        sha256 = compute_sha256(content_bytes)

        error = self._check_constraints(name, force)
        if error is not None:
            return error

        content_str = self._prepare_content(
            content_str, name, source, sha256, is_remote, validation.load,
        )
        return self._write_and_reload(name, description, sha256, content_str)

    def _validate_content(
        self, content_bytes: bytes, expected_sha256: str,
    ) -> InstallResult | None:
        """Validate size, format, and optional SHA256. Returns error or None."""
        if not validate_skill_size(content_bytes, max_size=self._max_skill_size):
            return InstallResult(
                success=False,
                error=(
                    f"Skill exceeds maximum size of {self._max_skill_size} bytes "
                    f"(got {len(content_bytes)} bytes)"
                ),
            )
        content_str = content_bytes.decode("utf-8", errors="replace")
        validation = validate_skill_content(content_str)
        if not validation.valid:
            return InstallResult(
                success=False,
                error=f"Invalid skill format: {validation.error}",
            )
        sha256 = compute_sha256(content_bytes)
        if expected_sha256 and sha256 != expected_sha256:
            return InstallResult(
                success=False,
                error=(
                    f"SHA256 mismatch for '{validation.name}': "
                    f"expected {expected_sha256}, got {sha256}"
                ),
            )
        return None

    def _check_constraints(self, name: str, force: bool) -> InstallResult | None:
        """Check protected names and duplicates. Returns error or None."""
        if name in self._registry.protected_names:
            return InstallResult(
                success=False,
                error=f"Cannot install '{name}': name is protected (built-in skill)",
            )
        if not force and self._registry.get(name) is not None:
            return InstallResult(
                success=False,
                error=(
                    f"Skill '{name}' already exists. "
                    "Use force=True to overwrite."
                ),
            )
        return None

    def _prepare_content(
        self,
        content_str: str,
        name: str,
        source: str,
        sha256: str,
        is_remote: bool,
        load_mode: str,
    ) -> str:
        """Downgrade load mode if needed and inject metadata."""
        if is_remote and load_mode == "always":
            content_str = self._replace_load_mode(content_str, "always", "on_demand")
            logger.info(
                f"Remote skill '{name}' had load:always; downgraded to on_demand"
            )
        return self._inject_metadata(content_str, source=source, sha256=sha256)

    def _write_and_reload(
        self, name: str, description: str, sha256: str, content_str: str,
    ) -> InstallResult:
        """Write skill file to disk and reload registry."""
        dest = self._user_dir / f"{name}.md"
        dest.write_text(content_str, encoding="utf-8")
        logger.info(f"Installed skill '{name}' → {dest}")
        self._registry.reload()
        return InstallResult(
            success=True,
            name=name,
            description=description,
            sha256=sha256,
            content=content_str,
        )

    # ------------------------------------------------------------------
    # Remove
    # ------------------------------------------------------------------

    def remove(self, name: str) -> InstallResult:
        """Remove a user-installed skill by name.

        Rejects removal of built-in (protected) skills.
        """
        # Reject protected (builtin) names
        if name in self._registry.protected_names:
            return InstallResult(
                success=False,
                error=f"Cannot remove '{name}': it is a built-in skill",
            )

        dest = self._user_dir / f"{name}.md"
        if not dest.exists():
            return InstallResult(
                success=False,
                error=f"Skill '{name}' not found in user skills directory",
            )

        dest.unlink()
        logger.info(f"Removed skill '{name}' from {self._user_dir}")
        self._registry.reload()

        return InstallResult(success=True, name=name)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(self, name: str) -> InstallResult:
        """Re-download and reinstall a skill using its stored source metadata."""
        skill = self._registry.get(name)
        if skill is None:
            return InstallResult(
                success=False,
                error=f"Skill '{name}' is not installed",
            )

        source = self._extract_frontmatter_field(
            skill.file_path.read_text(encoding="utf-8"), "source"
        )

        if not source:
            return InstallResult(
                success=False,
                error=f"Skill '{name}' has no source metadata; cannot auto-update",
            )

        return await self.install_from_source(source, force=True)

    # ------------------------------------------------------------------
    # Preview helper
    # ------------------------------------------------------------------

    def get_preview(self, content_bytes: bytes) -> str:
        """Return a short description preview from the skill content."""
        content_str = content_bytes.decode("utf-8", errors="replace")
        validation = validate_skill_content(content_str)
        if not validation.valid:
            return f"(invalid skill: {validation.error})"
        return f"{validation.name}: {validation.description}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _inject_metadata(self, content: str, source: str, sha256: str) -> str:
        """Insert or replace source and sha256 fields in the front-matter block."""
        match = _FRONT_MATTER_RE.match(content)
        if not match:
            return content

        front_matter = match.group(1)
        rest = content[match.end():]

        # Remove any existing source/sha256 lines
        lines = [
            line for line in front_matter.splitlines()
            if not line.strip().startswith("source:")
            and not line.strip().startswith("sha256:")
        ]
        lines.append(f"source: {source}")
        lines.append(f"sha256: {sha256}")

        new_front_matter = "\n".join(lines)
        return f"---\n{new_front_matter}\n---\n{rest}"

    def _replace_load_mode(self, content: str, old_mode: str, new_mode: str) -> str:
        """Replace load field value in front-matter block."""
        match = _FRONT_MATTER_RE.match(content)
        if not match:
            return content

        front_matter = match.group(1)
        rest = content[match.end():]

        new_lines = []
        for line in front_matter.splitlines():
            stripped = line.strip()
            if stripped == f"load: {old_mode}" or stripped == f"load:{old_mode}":
                new_lines.append(f"load: {new_mode}")
            else:
                new_lines.append(line)

        new_front_matter = "\n".join(new_lines)
        return f"---\n{new_front_matter}\n---\n{rest}"

    def _extract_frontmatter_field(self, full_content: str, field_name: str) -> str:
        """Extract a field value from the YAML front-matter section."""
        fm_match = _FRONT_MATTER_RE.match(full_content)
        if not fm_match:
            return ""
        front_matter = fm_match.group(1)
        pattern = re.compile(rf"^{re.escape(field_name)}:\s*(.+)$", re.MULTILINE)
        match = pattern.search(front_matter)
        return match.group(1).strip() if match else ""
