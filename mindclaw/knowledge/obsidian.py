# input: pathlib, re, yaml (frontmatter parsing)
# output: 导出 ObsidianKnowledge
# pos: Obsidian vault 读写/搜索/标签/链接，Phase 9.1
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Obsidian vault integration for MindClaw.

Provides read/write/search/list/tags/links operations on a local
Obsidian vault (a directory of Markdown files).
"""

from __future__ import annotations

import re
from pathlib import Path

from mindclaw.knowledge._text_utils import extract_snippet

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _validate_vault_path(vault: Path, rel_path: str) -> Path:
    """Resolve *rel_path* within *vault* and reject traversal attacks."""
    resolved = (vault / rel_path).resolve()
    if not resolved.is_relative_to(vault.resolve()):
        raise ValueError(f"Path outside vault: {rel_path}")
    return resolved


def _ensure_md_extension(path: Path) -> Path:
    """Append .md if the path has no suffix."""
    if path.suffix == "":
        return path.with_suffix(".md")
    return path


def _extract_frontmatter_tags(content: str) -> list[str]:
    """Extract tags from YAML frontmatter.

    Supports three Obsidian-compatible formats:
    - Inline list:  ``tags: [a, b, c]``
    - YAML list:    ``tags:\\n  - a\\n  - b``
    - Single value: ``tags: solo``
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return []
    fm_body = match.group(1)

    # Find the tags key
    tags_match = re.search(r"^tags:[^\S\n]*(.*)$", fm_body, re.MULTILINE)
    if not tags_match:
        return []

    rest = tags_match.group(1).strip()

    # Format 1: inline list  tags: [a, b, c]
    if rest.startswith("["):
        inner = rest.strip("[]")
        return [t.strip() for t in inner.split(",") if t.strip()]

    # Format 3: single value  tags: solo
    if rest:
        return [rest]

    # Format 2: YAML list  tags:\n  - a\n  - b
    tags: list[str] = []
    # Find lines after "tags:" that start with "  - "
    in_tags = False
    for line in fm_body.splitlines():
        if line.strip().startswith("tags:"):
            in_tags = True
            continue
        if in_tags:
            stripped = line.strip()
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip())
            else:
                break
    return tags


class ObsidianKnowledge:
    """Read, write, search, and inspect an Obsidian vault."""

    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path.resolve()

    # ------------------------------------------------------------------
    # read / write
    # ------------------------------------------------------------------

    def read_note(self, path: str) -> str:
        """Read a note. *path* is relative to vault root. .md auto-appended."""
        target = _validate_vault_path(self._vault, path)
        target = _ensure_md_extension(target)
        if not target.exists():
            raise FileNotFoundError(f"Note not found: {path}")
        return target.read_text(encoding="utf-8")

    def write_note(self, path: str, content: str) -> None:
        """Write (create or overwrite) a note. Directories created as needed."""
        target = _validate_vault_path(self._vault, path)
        target = _ensure_md_extension(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search_notes(self, query: str) -> list[dict]:
        """Full-text search across all .md files. Returns list of dicts
        with keys: path, title, snippet."""
        query_lower = query.lower()
        results: list[dict] = []

        for md_file in self._vault.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if query_lower not in text.lower():
                continue

            rel = str(md_file.relative_to(self._vault))
            title = _extract_title(text) or md_file.stem
            snippet = extract_snippet(text, query_lower)
            results.append({"path": rel, "title": title, "snippet": snippet})

        return results

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    def list_notes(self, folder: str = ".") -> list[dict]:
        """List entries in *folder* (relative to vault). Returns dicts
        with keys: name, type ('file' | 'dir')."""
        target = _validate_vault_path(self._vault, folder)
        if not target.exists():
            raise FileNotFoundError(f"Folder not found: {folder}")
        if not target.is_dir():
            raise FileNotFoundError(f"Not a directory: {folder}")

        entries: list[dict] = []
        for item in sorted(target.iterdir()):
            if item.name.startswith("."):
                continue
            entry_type = "dir" if item.is_dir() else "file"
            entries.append({"name": item.name, "type": entry_type})
        return entries

    # ------------------------------------------------------------------
    # tags
    # ------------------------------------------------------------------

    def get_tags(self) -> list[str]:
        """Collect all unique tags from frontmatter across the vault."""
        all_tags: set[str] = set()
        for md_file in self._vault.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            all_tags.update(_extract_frontmatter_tags(text))
        return sorted(all_tags)

    # ------------------------------------------------------------------
    # links
    # ------------------------------------------------------------------

    def get_links(self, path: str) -> list[str]:
        """Extract all [[wikilink]] targets from a note."""
        content = self.read_note(path)
        return _WIKILINK_RE.findall(content)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _extract_title(text: str) -> str:
    """Extract first heading (# ...) as title."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


