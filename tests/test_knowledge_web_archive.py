# input: knowledge/web_archive.py
# output: WebArchive 测试
# pos: Phase 9.3 网页收藏测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for WebArchive — fetch, save, search, and list web pages."""

import json
from pathlib import Path

import pytest

from mindclaw.knowledge.web_archive import WebArchive


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    return tmp_path / "web_archive"


@pytest.fixture
def archive(archive_dir: Path) -> WebArchive:
    return WebArchive(archive_dir=archive_dir, max_pages=100)


@pytest.fixture
def populated_archive(archive: WebArchive, archive_dir: Path) -> WebArchive:
    """Pre-populate archive with two saved pages."""
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Page 1
    p1 = archive_dir / "abc123.md"
    p1.write_text(
        "---\nurl: https://example.com/article\n"
        "title: Example Article\n"
        "saved_at: 2026-03-10T10:00:00\n---\n\n"
        "# Example Article\n\nThis is about Python programming.\n",
        encoding="utf-8",
    )

    # Page 2
    p2 = archive_dir / "def456.md"
    p2.write_text(
        "---\nurl: https://example.com/other\n"
        "title: Other Page\n"
        "saved_at: 2026-03-09T15:00:00\n---\n\n"
        "# Other Page\n\nInformation about Rust.\n",
        encoding="utf-8",
    )

    # Index
    index = [
        {
            "id": "abc123",
            "url": "https://example.com/article",
            "title": "Example Article",
            "saved_at": "2026-03-10T10:00:00",
        },
        {
            "id": "def456",
            "url": "https://example.com/other",
            "title": "Other Page",
            "saved_at": "2026-03-09T15:00:00",
        },
    ]
    (archive_dir / "index.json").write_text(json.dumps(index), encoding="utf-8")

    return archive


# ---- save ----


class TestSave:
    def test_save_creates_file_and_index(
        self, archive: WebArchive, archive_dir: Path
    ) -> None:
        html = "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"
        result = archive.save(
            url="https://example.com/test",
            html=html,
            title="Test Page",
        )

        assert result["url"] == "https://example.com/test"
        assert result["title"] == "Test Page"
        assert "id" in result

        # File should exist
        saved_file = archive_dir / f"{result['id']}.md"
        assert saved_file.exists()
        content = saved_file.read_text(encoding="utf-8")
        assert "Hello world" in content

        # Index should be updated
        index_path = archive_dir / "index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text())
        assert len(index) == 1
        assert index[0]["url"] == "https://example.com/test"

    def test_save_deduplicates_by_url(
        self, populated_archive: WebArchive, archive_dir: Path
    ) -> None:
        populated_archive.save(
            url="https://example.com/article",
            html="<html><body>Updated content</body></html>",
            title="Example Article Updated",
        )

        # Should overwrite existing, same id
        index = json.loads((archive_dir / "index.json").read_text())
        urls = [e["url"] for e in index]
        assert urls.count("https://example.com/article") == 1

    def test_save_respects_max_pages(
        self, archive_dir: Path
    ) -> None:
        archive = WebArchive(archive_dir=archive_dir, max_pages=1)

        archive.save("https://a.com", "<body>A</body>", "A")
        archive.save("https://b.com", "<body>B</body>", "B")

        index = json.loads((archive_dir / "index.json").read_text())
        assert len(index) <= 1


# ---- search_saved ----


class TestSearchSaved:
    def test_search_finds_matching(self, populated_archive: WebArchive) -> None:
        results = populated_archive.search_saved("Python")
        assert len(results) >= 1
        assert any("Python" in r.get("snippet", "") for r in results)

    def test_search_by_title(self, populated_archive: WebArchive) -> None:
        results = populated_archive.search_saved("Example Article")
        assert len(results) >= 1

    def test_search_no_match(self, populated_archive: WebArchive) -> None:
        results = populated_archive.search_saved("xyznonexistent")
        assert results == []

    def test_search_case_insensitive(self, populated_archive: WebArchive) -> None:
        results = populated_archive.search_saved("python")
        assert len(results) >= 1


# ---- list_saved ----


class TestListSaved:
    def test_list_returns_all(self, populated_archive: WebArchive) -> None:
        items = populated_archive.list_saved()
        assert len(items) == 2

    def test_list_items_have_fields(self, populated_archive: WebArchive) -> None:
        items = populated_archive.list_saved()
        for item in items:
            assert "id" in item
            assert "url" in item
            assert "title" in item
            assert "saved_at" in item

    def test_list_empty_archive(self, archive: WebArchive) -> None:
        items = archive.list_saved()
        assert items == []
