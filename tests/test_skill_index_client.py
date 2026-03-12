# input: mindclaw.skills.index_client, pytest, unittest.mock
# output: IndexClient 测试：解析/搜索/标签过滤/解析/缓存/离线降级
# pos: 验证 IndexClient 的 IndexEntry 解析、search/search_by_tag/resolve 以及缓存降级行为
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for mindclaw.skills.index_client (IndexEntry + IndexClient)."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.skills.index_client import IndexClient, IndexEntry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_index() -> dict:
    """Minimal index dict with two skills."""
    return {
        "version": 1,
        "skills": [
            {
                "name": "code-review",
                "description": "Automated code review assistant",
                "source": "github:org/skills/code-review.md",
                "sha256": "abc123def456" * 5 + "abcd",  # 64 hex chars
                "verified": True,
                "tags": ["development", "review"],
                "size_bytes": 1024,
                "commit_sha": "deadbeef",
            },
            {
                "name": "debug-guide",
                "description": "Step-by-step debugging guide",
                "source": "github:org/skills/debug-guide.md",
                "sha256": "fedcba987654" * 5 + "fedc",  # 64 hex chars
                "verified": False,
                "tags": ["development", "debugging"],
                "size_bytes": 2048,
                "commit_sha": "cafebabe",
            },
        ],
    }


# ---------------------------------------------------------------------------
# IndexEntry.from_dict tests
# ---------------------------------------------------------------------------


class TestIndexEntryFromDict:
    def test_parses_all_fields(self, sample_index):
        raw = sample_index["skills"][0]
        entry = IndexEntry.from_dict(raw)

        assert entry.name == "code-review"
        assert entry.description == "Automated code review assistant"
        assert entry.source == "github:org/skills/code-review.md"
        assert entry.sha256 == raw["sha256"]
        assert entry.verified is True
        assert entry.tags == ["development", "review"]
        assert entry.size_bytes == 1024
        assert entry.commit_sha == "deadbeef"

    def test_parses_unverified_entry(self, sample_index):
        raw = sample_index["skills"][1]
        entry = IndexEntry.from_dict(raw)

        assert entry.name == "debug-guide"
        assert entry.verified is False

    def test_tags_default_to_empty_list_when_missing(self):
        raw = {
            "name": "minimal",
            "description": "desc",
            "source": "github:org/minimal.md",
            "sha256": "a" * 64,
            "verified": False,
            "size_bytes": 100,
            "commit_sha": "abc",
        }
        entry = IndexEntry.from_dict(raw)
        assert entry.tags == []

    def test_entry_is_frozen(self, sample_index):
        entry = IndexEntry.from_dict(sample_index["skills"][0])
        with pytest.raises((AttributeError, TypeError)):
            entry.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IndexClient.search tests
# ---------------------------------------------------------------------------


class TestSearchByQuery:
    @pytest.mark.asyncio
    async def test_search_code_review_returns_first(self, sample_index, tmp_path):
        """Pre-populated cache: 'code review' should return code-review first."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "skill-index.json"
        cache_file.write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search("code review")

        assert len(results) >= 1
        assert results[0].name == "code-review"

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_all(self, sample_index, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search("")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, sample_index, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search("CODE REVIEW")

        assert any(r.name == "code-review" for r in results)

    @pytest.mark.asyncio
    async def test_search_no_match_returns_empty(self, sample_index, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search("quantum entanglement xyz")

        assert results == []


# ---------------------------------------------------------------------------
# IndexClient.search_by_tag tests
# ---------------------------------------------------------------------------


class TestSearchByTag:
    @pytest.mark.asyncio
    async def test_search_by_tag_returns_only_matching(self, sample_index, tmp_path):
        """search_by_tag('debugging') returns only debug-guide."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search_by_tag("debugging")

        assert len(results) == 1
        assert results[0].name == "debug-guide"

    @pytest.mark.asyncio
    async def test_search_by_tag_shared_tag_returns_both(self, sample_index, tmp_path):
        """Both skills share the 'development' tag."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search_by_tag("development")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_by_tag_no_match_returns_empty(self, sample_index, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search_by_tag("nonexistent-tag")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_tag_exact_match_only(self, sample_index, tmp_path):
        """'debug' should not match tag 'debugging' (exact match required)."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        results = await client.search_by_tag("debug")

        assert results == []


# ---------------------------------------------------------------------------
# IndexClient.resolve tests
# ---------------------------------------------------------------------------


class TestResolveName:
    @pytest.mark.asyncio
    async def test_resolve_returns_correct_entry(self, sample_index, tmp_path):
        """resolve('code-review') returns entry with correct sha256."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        entry = await client.resolve("code-review")

        assert entry is not None
        assert entry.name == "code-review"
        assert entry.sha256 == sample_index["skills"][0]["sha256"]
        assert entry.verified is True

    @pytest.mark.asyncio
    async def test_resolve_unknown_name_returns_none(self, sample_index, tmp_path):
        """resolve('nonexistent') returns None."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )
        entry = await client.resolve("nonexistent")

        assert entry is None


# ---------------------------------------------------------------------------
# Cache + offline fallback tests
# ---------------------------------------------------------------------------


class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_stale_cache_used_when_offline(self, sample_index, tmp_path):
        """Expired cache + network failure should still return results."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # Write an expired cache (fetched 2 hours ago, TTL=1 hour)
        stale_ts = time.time() - 7200
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": stale_ts, "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )

        # Simulate network failure by raising on AsyncClient.__aenter__
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(side_effect=Exception("Network unreachable"))
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mindclaw.skills.index_client.httpx.AsyncClient", return_value=mock_async_client):
            results = await client.search("code review")

        assert len(results) >= 1
        assert results[0].name == "code-review"

    @pytest.mark.asyncio
    async def test_no_cache_and_offline_returns_empty(self, tmp_path):
        """No cache file + network failure should return []."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # No cache file present

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(side_effect=Exception("Network unreachable"))
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mindclaw.skills.index_client.httpx.AsyncClient", return_value=mock_async_client):
            results = await client.search("anything")

        assert results == []

    @pytest.mark.asyncio
    async def test_fresh_cache_not_refetched(self, sample_index, tmp_path):
        """A fresh cache should be served without making a network call."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "skill-index.json").write_text(
            json.dumps({"fetched_at": time.time(), "data": sample_index})
        )

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )

        with patch("mindclaw.skills.index_client.httpx.AsyncClient") as mock_cls:
            await client.search("code review")
            # AsyncClient should never be instantiated
            mock_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_remote_fetch_writes_cache(self, sample_index, tmp_path):
        """Successful remote fetch should write cache to disk."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        # No cache file

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=sample_index)

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.get = AsyncMock(return_value=mock_response)

        with patch("mindclaw.skills.index_client.httpx.AsyncClient", return_value=mock_async_client):
            await client.search("debug")

        cache_file = cache_dir / "skill-index.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert "fetched_at" in cached
        assert cached["data"] == sample_index

    @pytest.mark.asyncio
    async def test_cache_dir_missing_does_not_crash(self, sample_index, tmp_path):
        """If cache_dir does not exist yet, client should create it when writing."""
        cache_dir = tmp_path / "cache" / "nested"
        # Do NOT create the directory

        client = IndexClient(
            index_url="https://example.com/index.json",
            cache_dir=cache_dir,
            cache_ttl=3600,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=sample_index)

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.get = AsyncMock(return_value=mock_response)

        with patch("mindclaw.skills.index_client.httpx.AsyncClient", return_value=mock_async_client):
            results = await client.search("debug")

        assert isinstance(results, list)
