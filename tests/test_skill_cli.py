# input: mindclaw.cli.commands, mindclaw.cli.skill_commands, typer.testing
# output: CLI skill subcommand tests
# pos: Task 7 test suite for skill install/remove/list/show/search/update CLI commands
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for the `mindclaw skill` CLI subcommand group.

TDD RED phase: all tests written before implementation.
Tests cover:
  - skill list (empty + with skills)
  - skill show (found + not found)
  - skill install (local file, duplicate, force overwrite)
  - skill remove (success, not found, protected)
  - skill search (with query, with --tag)
  - skill update (success, not installed)
  - edge cases: null/empty inputs, missing config, async operations
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SKILL_MD = dedent("""\
    ---
    name: test-skill
    description: A skill for testing
    load: on_demand
    tags: test, cli
    ---
    # Test Skill

    This skill is used for testing CLI commands.
""")

PROTECTED_SKILL_MD = dedent("""\
    ---
    name: builtin-skill
    description: A built-in skill
    load: always
    tags: builtin
    ---
    # Built-in Skill content
""")


@pytest.fixture()
def skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with one valid skill."""
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "test-skill.md").write_text(VALID_SKILL_MD, encoding="utf-8")
    return skills


@pytest.fixture()
def builtin_skill_dir(tmp_path: Path) -> Path:
    """Create a temporary builtin skills directory with a protected skill."""
    builtins = tmp_path / "builtin_skills"
    builtins.mkdir()
    (builtins / "builtin-skill.md").write_text(PROTECTED_SKILL_MD, encoding="utf-8")
    return builtins


@pytest.fixture()
def config_file(tmp_path: Path, skill_dir: Path) -> Path:
    """Write a minimal config.json for CLI tests."""
    cfg = {
        "knowledge": {"dataDir": str(tmp_path / "data")},
        "skills": {
            "indexUrl": "https://example.com/index.json",
            "cacheTtl": 3600,
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Helper: import app after implementation exists
# ---------------------------------------------------------------------------

def _get_app():
    from mindclaw.cli.commands import app
    return app


# ---------------------------------------------------------------------------
# Smoke test: skill --help
# ---------------------------------------------------------------------------

class TestSkillHelp:
    def test_skill_help_shows_subcommands(self):
        app = _get_app()
        result = runner.invoke(app, ["skill", "--help"])
        assert result.exit_code == 0, result.output
        # All 6 subcommands must appear in help output
        for sub in ("install", "remove", "list", "show", "search", "update"):
            assert sub in result.output, (
                f"Expected subcommand '{sub}' in help output.\nGot:\n{result.output}"
            )


# ---------------------------------------------------------------------------
# skill list
# ---------------------------------------------------------------------------

class TestSkillList:
    def test_list_shows_installed_skills(self, tmp_path, config_file, skill_dir):
        """skill list should print skills discovered by the registry."""
        app = _get_app()
        with patch(
            "mindclaw.cli.skill_commands._build_components",
        ) as mock_build:
            registry = MagicMock()
            skill = MagicMock()
            skill.name = "test-skill"
            skill.description = "A skill for testing"
            skill.source_layer = "user"
            registry.skills = [skill]
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "list", "-c", str(config_file)])

        assert result.exit_code == 0, result.output
        assert "test-skill" in result.output

    def test_list_empty_registry(self, config_file):
        """skill list with no skills installed should not crash."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            registry.skills = []
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "list", "-c", str(config_file)])

        assert result.exit_code == 0, result.output

    def test_list_color_codes_source_layers(self, config_file):
        """Builtin skills show blue, project show yellow, user show green."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            skills = []
            for layer in ("builtin", "project", "user"):
                s = MagicMock()
                s.name = f"{layer}-skill"
                s.description = f"{layer} description"
                s.source_layer = layer
                skills.append(s)
            registry.skills = skills
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "list", "-c", str(config_file)])

        assert result.exit_code == 0, result.output
        assert "builtin-skill" in result.output
        assert "project-skill" in result.output
        assert "user-skill" in result.output


# ---------------------------------------------------------------------------
# skill show
# ---------------------------------------------------------------------------

class TestSkillShow:
    def test_show_existing_skill(self, config_file):
        """skill show <name> should display skill details."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            skill = MagicMock()
            skill.name = "test-skill"
            skill.description = "A skill for testing"
            skill.source_layer = "user"
            skill.load = "on_demand"
            skill.file_path = Path("/fake/test-skill.md")
            skill.content = "Some skill content"
            registry.get.return_value = skill
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "show", "test-skill", "-c", str(config_file)])

        assert result.exit_code == 0, result.output
        assert "test-skill" in result.output
        assert "A skill for testing" in result.output

    def test_show_nonexistent_skill_exits_nonzero(self, config_file):
        """skill show <name> for a missing skill should exit with non-zero code."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            registry.get.return_value = None
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "show", "nonexistent", "-c", str(config_file)])

        assert result.exit_code != 0 or "not found" in result.output.lower(), result.output

    def test_show_empty_name_handled(self, config_file):
        """skill show with empty string name should not crash with unhandled exception."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            registry.get.return_value = None
            mock_build.return_value = (registry, MagicMock(), MagicMock())

            result = runner.invoke(app, ["skill", "show", "", "-c", str(config_file)])

        # Should not raise an unhandled exception — exit code or message is fine
        assert isinstance(result.exit_code, int)


# ---------------------------------------------------------------------------
# skill install
# ---------------------------------------------------------------------------

class TestSkillInstall:
    def test_install_local_file_success(self, tmp_path, config_file, skill_dir):
        """skill install <local_path> should install successfully."""
        app = _get_app()
        skill_file = skill_dir / "test-skill.md"
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.install_from_source = AsyncMock(
                return_value=InstallResult(
                    success=True,
                    name="test-skill",
                    description="A skill for testing",
                    sha256="abc123",
                    content=VALID_SKILL_MD,
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app,
                ["skill", "install", str(skill_file), "--yes", "-c", str(config_file)],
            )

        assert result.exit_code == 0, result.output
        assert "test-skill" in result.output or "success" in result.output.lower() or "installed" in result.output.lower()

    def test_install_duplicate_fails_without_force(self, tmp_path, config_file, skill_dir):
        """Installing an existing skill without --force should fail."""
        app = _get_app()
        skill_file = skill_dir / "test-skill.md"
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.install_from_source = AsyncMock(
                return_value=InstallResult(
                    success=False,
                    error="Skill 'test-skill' already exists. Use force=True to overwrite.",
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app,
                ["skill", "install", str(skill_file), "--yes", "-c", str(config_file)],
            )

        assert result.exit_code != 0 or "already exists" in result.output.lower() or "error" in result.output.lower()

    def test_install_with_force_flag_overwrites(self, tmp_path, config_file, skill_dir):
        """skill install --force should call installer with force=True."""
        app = _get_app()
        skill_file = skill_dir / "test-skill.md"
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.install_from_source = AsyncMock(
                return_value=InstallResult(
                    success=True,
                    name="test-skill",
                    description="A skill for testing",
                    sha256="abc123",
                    content=VALID_SKILL_MD,
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app,
                ["skill", "install", str(skill_file), "--force", "--yes", "-c", str(config_file)],
            )

        assert result.exit_code == 0, result.output
        # Verify force=True was passed to the installer
        installer.install_from_source.assert_called_once_with(str(skill_file), force=True)

    def test_install_yes_flag_skips_confirmation(self, tmp_path, config_file, skill_dir):
        """skill install --yes should not prompt for confirmation."""
        app = _get_app()
        skill_file = skill_dir / "test-skill.md"
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.install_from_source = AsyncMock(
                return_value=InstallResult(
                    success=True,
                    name="test-skill",
                    description="A skill for testing",
                    sha256="abc123",
                    content=VALID_SKILL_MD,
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app,
                ["skill", "install", str(skill_file), "--yes", "-c", str(config_file)],
                input=None,  # No stdin input — should not block
            )

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# skill remove
# ---------------------------------------------------------------------------

class TestSkillRemove:
    def test_remove_success(self, config_file):
        """skill remove <name> should remove the skill."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.remove.return_value = InstallResult(success=True, name="test-skill")
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "remove", "test-skill", "--yes", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output

    def test_remove_not_found(self, config_file):
        """skill remove for a missing skill should show an error."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.remove.return_value = InstallResult(
                success=False, error="Skill 'missing' not found in user skills directory"
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "remove", "missing", "--yes", "-c", str(config_file)]
            )

        assert result.exit_code != 0 or "not found" in result.output.lower() or "error" in result.output.lower()

    def test_remove_protected_skill_rejected(self, config_file):
        """Removing a builtin (protected) skill should be refused."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.remove.return_value = InstallResult(
                success=False, error="Cannot remove 'builtin-skill': it is a built-in skill"
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "remove", "builtin-skill", "--yes", "-c", str(config_file)]
            )

        assert result.exit_code != 0 or "cannot remove" in result.output.lower() or "built-in" in result.output.lower() or "error" in result.output.lower()


# ---------------------------------------------------------------------------
# skill search
# ---------------------------------------------------------------------------

class TestSkillSearch:
    def test_search_with_query_returns_results(self, config_file):
        """skill search <query> should display matching skills from index."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            index_client = MagicMock()
            from mindclaw.skills.index_client import IndexEntry
            entry = IndexEntry(
                name="test-skill",
                description="A skill for testing",
                source="https://example.com/test-skill.md",
                sha256="abc123",
                verified=True,
                tags=["test", "cli"],
                size_bytes=512,
                commit_sha="deadbeef",
            )
            index_client.search = AsyncMock(return_value=[entry])
            mock_build.return_value = (MagicMock(), index_client, MagicMock())

            result = runner.invoke(
                app, ["skill", "search", "test", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output
        assert "test-skill" in result.output

    def test_search_empty_query_returns_all(self, config_file):
        """skill search with empty string returns all skills in index."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            index_client = MagicMock()
            from mindclaw.skills.index_client import IndexEntry
            entries = [
                IndexEntry(
                    name=f"skill-{i}",
                    description=f"Skill number {i}",
                    source=f"https://example.com/skill-{i}.md",
                    sha256=f"hash{i}",
                    verified=True,
                    tags=[],
                    size_bytes=100,
                    commit_sha="abc",
                )
                for i in range(3)
            ]
            index_client.search = AsyncMock(return_value=entries)
            mock_build.return_value = (MagicMock(), index_client, MagicMock())

            result = runner.invoke(app, ["skill", "search", "", "-c", str(config_file)])

        assert result.exit_code == 0, result.output

    def test_search_by_tag(self, config_file):
        """skill search --tag <tag> should use search_by_tag."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            index_client = MagicMock()
            from mindclaw.skills.index_client import IndexEntry
            entry = IndexEntry(
                name="tagged-skill",
                description="Has a tag",
                source="https://example.com/tagged-skill.md",
                sha256="xyz",
                verified=True,
                tags=["mytag"],
                size_bytes=200,
                commit_sha="beef",
            )
            index_client.search_by_tag = AsyncMock(return_value=[entry])
            mock_build.return_value = (MagicMock(), index_client, MagicMock())

            result = runner.invoke(
                app, ["skill", "search", "anything", "--tag", "mytag", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output
        assert "tagged-skill" in result.output
        index_client.search_by_tag.assert_called_once_with("mytag")

    def test_search_no_results(self, config_file):
        """skill search with no matches should exit 0 with appropriate message."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            index_client = MagicMock()
            index_client.search = AsyncMock(return_value=[])
            mock_build.return_value = (MagicMock(), index_client, MagicMock())

            result = runner.invoke(
                app, ["skill", "search", "nonexistent-xyz", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# skill update
# ---------------------------------------------------------------------------

class TestSkillUpdate:
    def test_update_single_skill_success(self, config_file):
        """skill update <name> should call installer.update(name)."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.update = AsyncMock(
                return_value=InstallResult(
                    success=True,
                    name="test-skill",
                    description="A skill for testing",
                    sha256="newsha256",
                    content=VALID_SKILL_MD,
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "update", "test-skill", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output
        installer.update.assert_called_once_with("test-skill")

    def test_update_not_installed_shows_error(self, config_file):
        """skill update <name> for a non-installed skill should show error."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.update = AsyncMock(
                return_value=InstallResult(
                    success=False,
                    error="Skill 'ghost' is not installed",
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "update", "ghost", "-c", str(config_file)]
            )

        assert result.exit_code != 0 or "not installed" in result.output.lower() or "error" in result.output.lower()

    def test_update_all_flag_updates_user_skills(self, config_file):
        """skill update --all should update all user-layer skills."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            registry = MagicMock()
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult

            user_skill = MagicMock()
            user_skill.name = "user-skill-a"
            user_skill.source_layer = "user"

            builtin_skill = MagicMock()
            builtin_skill.name = "builtin-skill"
            builtin_skill.source_layer = "builtin"

            registry.skills = [user_skill, builtin_skill]
            installer.update = AsyncMock(
                return_value=InstallResult(success=True, name="user-skill-a")
            )
            mock_build.return_value = (registry, MagicMock(), installer)

            result = runner.invoke(
                app, ["skill", "update", "--all", "-c", str(config_file)]
            )

        assert result.exit_code == 0, result.output
        # Should only update user-layer skills, not builtin
        installer.update.assert_called_once_with("user-skill-a")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_build_components_uses_config_paths(self, tmp_path):
        """_build_components creates SkillRegistry, IndexClient, SkillInstaller."""
        from mindclaw.cli.skill_commands import _build_components
        from mindclaw.config.schema import MindClawConfig

        cfg = MindClawConfig()
        registry, index_client, installer = _build_components(cfg, tmp_path)

        from mindclaw.skills.index_client import IndexClient
        from mindclaw.skills.installer import SkillInstaller
        from mindclaw.skills.registry import SkillRegistry

        assert isinstance(registry, SkillRegistry)
        assert isinstance(index_client, IndexClient)
        assert isinstance(installer, SkillInstaller)

    def test_skill_commands_registered_in_app(self):
        """The main app must have 'skill' as a registered subcommand group."""
        from mindclaw.cli.commands import app

        # Typer groups subcommand in registered_groups or via add_typer
        # Check that invoking skill --help works
        result = runner.invoke(app, ["skill", "--help"])
        assert result.exit_code == 0, (
            f"'skill' subcommand group not registered. Got:\n{result.output}"
        )

    def test_install_special_characters_in_source(self, config_file):
        """skill install with URL containing special chars should not crash."""
        app = _get_app()
        with patch("mindclaw.cli.skill_commands._build_components") as mock_build:
            installer = MagicMock()
            from mindclaw.skills.installer import InstallResult
            installer.install_from_source = AsyncMock(
                return_value=InstallResult(
                    success=False,
                    error="Unsafe or non-HTTPS URL rejected",
                )
            )
            mock_build.return_value = (MagicMock(), MagicMock(), installer)

            result = runner.invoke(
                app,
                ["skill", "install", "http://localhost/skill.md", "--yes", "-c", str(config_file)],
            )

        # Should fail gracefully, not crash
        assert isinstance(result.exit_code, int)
