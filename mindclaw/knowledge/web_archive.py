# input: pathlib, json, hashlib, datetime, knowledge/_text_utils.py
# output: 导出 WebArchive
# pos: 网页收藏系统 — 抓取/存储/搜索/列出网页，Phase 9.3
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Web archive for MindClaw.

Saves web pages as Markdown files with YAML frontmatter.
Maintains an index.json for fast listing and metadata search.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from mindclaw.knowledge._text_utils import extract_snippet, html_to_text


def _url_to_id(url: str) -> str:
    """Deterministic short ID from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def _validate_url(url: str) -> None:
    """Reject strings that are not valid http(s) URLs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"Invalid URL: {url}")


def _sanitize_frontmatter(value: str) -> str:
    """Strip newlines and quotes to prevent YAML frontmatter injection."""
    return value.replace("\n", " ").replace("\r", "").replace('"', "'")


class WebArchive:
    """Save, search, and list archived web pages."""

    def __init__(self, archive_dir: Path, max_pages: int = 1000) -> None:
        self._dir = archive_dir
        self._max_pages = max_pages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, url: str, html: str, title: str) -> dict:
        """Save a web page. Returns metadata dict with id, url, title, saved_at."""
        _validate_url(url)
        self._dir.mkdir(parents=True, exist_ok=True)

        page_id = _url_to_id(url)
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        body_text = html_to_text(html)

        safe_url = _sanitize_frontmatter(url)
        safe_title = _sanitize_frontmatter(title)

        # Build Markdown with frontmatter
        content = (
            f"---\nurl: \"{safe_url}\"\ntitle: \"{safe_title}\"\nsaved_at: {now}\n---\n\n"
            f"# {safe_title}\n\n{body_text}\n"
        )

        # Write file
        file_path = self._dir / f"{page_id}.md"
        file_path.write_text(content, encoding="utf-8")

        meta = {"id": page_id, "url": url, "title": title, "saved_at": now}

        # Update index
        index = self._load_index()
        index = [e for e in index if e["url"] != url]  # deduplicate
        index.append(meta)

        # Enforce max_pages (remove oldest)
        if len(index) > self._max_pages:
            to_remove = index[: len(index) - self._max_pages]
            for entry in to_remove:
                old_file = self._dir / f"{entry['id']}.md"
                if old_file.exists():
                    old_file.unlink()
            index = index[len(index) - self._max_pages :]

        self._save_index(index)
        logger.info(f"Archived: {url} -> {page_id}")
        return meta

    def search_saved(self, query: str) -> list[dict]:
        """Search saved pages by title and content. Returns list of dicts
        with id, url, title, snippet."""
        query_lower = query.lower()
        results: list[dict] = []

        for md_file in self._dir.glob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if query_lower not in text.lower():
                continue

            meta = self._parse_frontmatter(text)
            snippet = extract_snippet(text, query_lower)
            results.append({
                "id": md_file.stem,
                "url": meta.get("url", ""),
                "title": meta.get("title", md_file.stem),
                "snippet": snippet,
            })

        return results

    def list_saved(self) -> list[dict]:
        """List all saved pages from index. Returns list of metadata dicts."""
        return self._load_index()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_index(self) -> list[dict]:
        index_path = self._dir / "index.json"
        if not index_path.exists():
            return []
        try:
            return json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save_index(self, index: list[dict]) -> None:
        index_path = self._dir / "index.json"
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> dict:
        """Extract key-value pairs from YAML frontmatter."""
        if not text.startswith("---\n"):
            return {}
        end = text.find("\n---\n", 4)
        if end == -1:
            return {}
        fm_text = text[4:end]
        result: dict = {}
        for line in fm_text.splitlines():
            if ": " in line:
                key, _, value = line.partition(": ")
                result[key.strip()] = value.strip()
        return result

