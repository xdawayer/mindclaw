# input: httpx (async HTTP), pathlib, json, time, loguru
# output: 导出 IndexEntry (frozen dataclass), IndexClient (fetch/cache/search)
# pos: 技能索引客户端，负责远程获取 + 本地缓存 + 搜索/标签过滤/精确解析
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill index client: fetch, cache, search, and resolve index entries."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

_CACHE_FILENAME = "skill-index.json"
_FETCH_TIMEOUT = 30.0


@dataclass(frozen=True)
class IndexEntry:
    """A single skill entry parsed from the remote index."""

    name: str
    description: str
    source: str
    sha256: str
    verified: bool
    tags: list[str]
    size_bytes: int
    commit_sha: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexEntry:
        """Parse an IndexEntry from a raw index dict."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            source=data.get("source", ""),
            sha256=data.get("sha256", ""),
            verified=bool(data.get("verified", False)),
            tags=list(data.get("tags", [])),
            size_bytes=int(data.get("size_bytes", 0)),
            commit_sha=data.get("commit_sha", ""),
        )


class IndexClient:
    """Fetch, cache, and search the remote skill index.

    Cache file format:
        {"fetched_at": <unix timestamp float>, "data": <index dict>}
    Saved to ``cache_dir / "skill-index.json"``.
    """

    def __init__(
        self,
        index_url: str,
        cache_dir: Path,
        cache_ttl: float = 3600.0,
    ) -> None:
        self._index_url = index_url
        self._cache_dir = cache_dir
        self._cache_ttl = cache_ttl
        self._cache_path = cache_dir / _CACHE_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, query: str) -> list[IndexEntry]:
        """Case-insensitive substring search across name, description, tags.

        Scoring:
          - name match   → 2 points
          - description  → 1 point
          - any tag      → 1 point (per matching tag)

        Empty query returns all entries sorted by name.
        Results are sorted by score descending, then name ascending.
        """
        entries = await self._get_entries()
        q = query.strip().lower()
        if not q:
            return sorted(entries, key=lambda e: e.name)

        scored: list[tuple[int, IndexEntry]] = []
        for entry in entries:
            score = 0
            if q in entry.name.lower():
                score += 2
            if q in entry.description.lower():
                score += 1
            for tag in entry.tags:
                if q in tag.lower():
                    score += 1
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda t: (-t[0], t[1].name))
        return [e for _, e in scored]

    async def search_by_tag(self, tag: str) -> list[IndexEntry]:
        """Return all entries whose tags list contains an exact match for ``tag``."""
        entries = await self._get_entries()
        return [e for e in entries if tag in e.tags]

    async def resolve(self, name: str) -> IndexEntry | None:
        """Return the entry with an exact name match, or None if not found."""
        entries = await self._get_entries()
        for entry in entries:
            if entry.name == name:
                return entry
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_entries(self) -> list[IndexEntry]:
        """Return parsed entries, using cache when fresh, fetching when stale."""
        cached = self._read_cache()
        if cached is not None:
            fetched_at, data = cached
            if time.time() - fetched_at < self._cache_ttl:
                logger.debug("skill-index: serving from fresh cache")
                return self._parse_entries(data)

        # Cache is stale or absent — try remote fetch
        try:
            data = await self._fetch_remote()
            self._write_cache(data)
            logger.debug("skill-index: fetched and cached from remote")
            return self._parse_entries(data)
        except Exception as exc:
            logger.warning(f"skill-index: remote fetch failed ({exc})")
            # Fall back to stale cache if available
            if cached is not None:
                logger.info("skill-index: using stale cache as fallback")
                _, data = cached
                return self._parse_entries(data)
            logger.warning("skill-index: no cache available, returning []")
            return []

    async def _fetch_remote(self) -> dict[str, Any]:
        """HTTP GET the index URL and return the parsed JSON dict."""
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            response = await client.get(self._index_url)
            response.raise_for_status()
            return response.json()

    def _read_cache(self) -> tuple[float, dict[str, Any]] | None:
        """Read the cache file. Returns (fetched_at, data) or None if missing/corrupt."""
        if not self._cache_path.exists():
            return None
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return float(raw["fetched_at"]), raw["data"]
        except Exception as exc:
            logger.debug(f"skill-index: cache read error ({exc}), treating as absent")
            return None

    def _write_cache(self, data: dict[str, Any]) -> None:
        """Write fetched index data to disk with a timestamp."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": time.time(), "data": data}
        self._cache_path.write_text(json.dumps(payload), encoding="utf-8")

    def _parse_entries(self, data: dict[str, Any]) -> list[IndexEntry]:
        """Parse the ``skills`` list from an index dict into IndexEntry objects."""
        entries: list[IndexEntry] = []
        for raw in data.get("skills", []):
            try:
                entries.append(IndexEntry.from_dict(raw))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(f"skill-index: skipping malformed entry ({exc})")
        return entries
