# input: knowledge/obsidian.py
# output: ObsidianKnowledge 测试
# pos: Phase 9.1 Obsidian 集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for ObsidianKnowledge — vault read/write/search/list/tags/links."""

from pathlib import Path

import pytest

from mindclaw.knowledge.obsidian import ObsidianKnowledge


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal Obsidian vault with test notes."""
    # Note with frontmatter + wikilinks
    note1 = tmp_path / "projects" / "mindclaw.md"
    note1.parent.mkdir(parents=True)
    note1.write_text(
        "---\ntags: [ai, python]\n---\n"
        "# MindClaw\n\nPersonal AI assistant. See [[architecture]].\n"
        "Also links to [[tools/web]].\n",
        encoding="utf-8",
    )

    # Plain note without frontmatter
    note2 = tmp_path / "daily" / "2026-03-10.md"
    note2.parent.mkdir(parents=True)
    note2.write_text(
        "# Daily Note\n\nWorked on MindClaw phase 9 today.\n",
        encoding="utf-8",
    )

    # Architecture note
    note3 = tmp_path / "architecture.md"
    note3.write_text(
        "---\ntags: [design]\n---\n# Architecture\n\nSix layers.\n",
        encoding="utf-8",
    )

    # Nested note for link target
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "web.md").write_text("# Web Tools\n\nHTTP stuff.\n", encoding="utf-8")

    return tmp_path


@pytest.fixture
def obsidian(vault: Path) -> ObsidianKnowledge:
    return ObsidianKnowledge(vault_path=vault)


# ---- read_note ----


class TestReadNote:
    def test_read_existing_note(self, obsidian: ObsidianKnowledge) -> None:
        content = obsidian.read_note("projects/mindclaw.md")
        assert "# MindClaw" in content
        assert "Personal AI assistant" in content

    def test_read_note_without_extension(self, obsidian: ObsidianKnowledge) -> None:
        content = obsidian.read_note("projects/mindclaw")
        assert "# MindClaw" in content

    def test_read_nonexistent_note_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(FileNotFoundError):
            obsidian.read_note("nonexistent.md")

    def test_read_outside_vault_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(ValueError, match="outside vault"):
            obsidian.read_note("../../etc/passwd")


# ---- write_note ----


class TestWriteNote:
    def test_write_new_note(self, obsidian: ObsidianKnowledge, vault: Path) -> None:
        obsidian.write_note("ideas/new-idea.md", "# New Idea\n\nSomething cool.\n")
        assert (vault / "ideas" / "new-idea.md").exists()
        assert "Something cool" in (vault / "ideas" / "new-idea.md").read_text()

    def test_write_overwrites_existing(
        self, obsidian: ObsidianKnowledge, vault: Path
    ) -> None:
        obsidian.write_note("architecture.md", "# Updated\n\nNew content.\n")
        assert "New content" in (vault / "architecture.md").read_text()

    def test_write_outside_vault_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(ValueError, match="outside vault"):
            obsidian.write_note("../outside.md", "bad")

    def test_write_adds_md_extension(
        self, obsidian: ObsidianKnowledge, vault: Path
    ) -> None:
        obsidian.write_note("test-note", "# Test\n")
        assert (vault / "test-note.md").exists()


# ---- search_notes ----


class TestSearchNotes:
    def test_search_finds_matching_notes(self, obsidian: ObsidianKnowledge) -> None:
        results = obsidian.search_notes("MindClaw")
        paths = [r["path"] for r in results]
        assert any("mindclaw.md" in p for p in paths)

    def test_search_returns_snippet(self, obsidian: ObsidianKnowledge) -> None:
        results = obsidian.search_notes("phase 9")
        assert len(results) >= 1
        assert "snippet" in results[0]
        assert "phase 9" in results[0]["snippet"].lower()

    def test_search_no_results(self, obsidian: ObsidianKnowledge) -> None:
        results = obsidian.search_notes("xyznonexistent")
        assert results == []

    def test_search_case_insensitive(self, obsidian: ObsidianKnowledge) -> None:
        results = obsidian.search_notes("mindclaw")
        assert len(results) >= 1


# ---- list_notes ----


class TestListNotes:
    def test_list_root(self, obsidian: ObsidianKnowledge) -> None:
        entries = obsidian.list_notes()
        names = [e["name"] for e in entries]
        assert "architecture.md" in names
        assert "projects" in names or "projects/" in names

    def test_list_subfolder(self, obsidian: ObsidianKnowledge) -> None:
        entries = obsidian.list_notes("projects")
        names = [e["name"] for e in entries]
        assert "mindclaw.md" in names

    def test_list_nonexistent_folder_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(FileNotFoundError):
            obsidian.list_notes("nonexistent")

    def test_list_outside_vault_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(ValueError, match="outside vault"):
            obsidian.list_notes("../../")

    def test_entries_have_type_field(self, obsidian: ObsidianKnowledge) -> None:
        entries = obsidian.list_notes()
        types = {e["type"] for e in entries}
        assert "file" in types or "dir" in types


# ---- get_tags ----


class TestGetTags:
    def test_collects_all_tags(self, obsidian: ObsidianKnowledge) -> None:
        tags = obsidian.get_tags()
        assert "ai" in tags
        assert "python" in tags
        assert "design" in tags

    def test_no_duplicates(self, obsidian: ObsidianKnowledge) -> None:
        tags = obsidian.get_tags()
        assert len(tags) == len(set(tags))

    def test_yaml_list_format_tags(self, vault: Path) -> None:
        """Tags in YAML list format: tags:\\n  - foo\\n  - bar."""
        note = vault / "yaml-list-tags.md"
        note.write_text(
            "---\ntags:\n  - workflow\n  - automation\n---\n# Note\n",
            encoding="utf-8",
        )
        obsidian = ObsidianKnowledge(vault_path=vault)
        tags = obsidian.get_tags()
        assert "workflow" in tags
        assert "automation" in tags

    def test_single_tag_string(self, vault: Path) -> None:
        """Tags as single string: tags: solo."""
        note = vault / "single-tag.md"
        note.write_text(
            "---\ntags: solo\n---\n# Note\n",
            encoding="utf-8",
        )
        obsidian = ObsidianKnowledge(vault_path=vault)
        tags = obsidian.get_tags()
        assert "solo" in tags


# ---- get_links ----


class TestGetLinks:
    def test_extracts_wikilinks(self, obsidian: ObsidianKnowledge) -> None:
        links = obsidian.get_links("projects/mindclaw.md")
        assert "architecture" in links
        assert "tools/web" in links

    def test_no_links_returns_empty(self, obsidian: ObsidianKnowledge) -> None:
        links = obsidian.get_links("daily/2026-03-10.md")
        assert links == []

    def test_links_from_nonexistent_raises(self, obsidian: ObsidianKnowledge) -> None:
        with pytest.raises(FileNotFoundError):
            obsidian.get_links("nonexistent.md")
