# input: mindclaw.skills.installer, mindclaw.skills.registry, mindclaw.skills.integrity
# output: 技能安装器完整测试套件
# pos: 验证 SkillInstaller 的安装/删除/更新/验证逻辑
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for SkillInstaller: install, remove, update, validation."""

from __future__ import annotations

from textwrap import dedent

import pytest

from mindclaw.skills.registry import SkillRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SKILL_CONTENT = dedent("""\
    ---
    name: my-skill
    description: A test skill
    load: on_demand
    ---

    # My Skill

    Do something useful.
""")

_ALWAYS_SKILL_CONTENT = dedent("""\
    ---
    name: always-skill
    description: Always loaded skill
    load: always
    ---

    # Always Skill

    Always in context.
""")

_TRANSLATE_SKILL_CONTENT = dedent("""\
    ---
    name: translate
    description: Translate text to a specified language
    load: on_demand
    ---

    # Translate

    Translate stuff.
""")

_INVALID_SKILL_NO_FRONTMATTER = "# Just a heading\nNo front-matter here.\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def installer_setup(tmp_path):
    """Create builtin dir (with translate.md), user dir (empty),
    build SkillRegistry([builtin, user]), and create SkillInstaller.
    """
    builtin_dir = tmp_path / "builtin_skills"
    builtin_dir.mkdir()
    (builtin_dir / "translate.md").write_text(_TRANSLATE_SKILL_CONTENT, encoding="utf-8")

    user_dir = tmp_path / "user_skills"
    user_dir.mkdir()

    registry = SkillRegistry([builtin_dir, user_dir])

    from mindclaw.skills.installer import SkillInstaller

    installer = SkillInstaller(
        user_skills_dir=user_dir,
        registry=registry,
        index_client=None,
        max_skill_size=8192,
    )

    return installer, user_dir, registry


# ---------------------------------------------------------------------------
# Install from local file
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_from_local_file(installer_setup, tmp_path):
    """Install a valid .md file: success, file on disk, registry updated."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(_VALID_SKILL_CONTENT, encoding="utf-8")

    result = await installer.install_from_local(skill_file)

    assert result.success is True
    assert result.name == "my-skill"
    assert (user_dir / "my-skill.md").exists()
    assert registry.get("my-skill") is not None


# ---------------------------------------------------------------------------
# Protected name rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_rejects_protected_name(installer_setup, tmp_path):
    """Trying to install a skill named 'translate' (a builtin) should fail."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "translate.md"
    skill_file.write_text(_TRANSLATE_SKILL_CONTENT, encoding="utf-8")

    result = await installer.install_from_local(skill_file)

    assert result.success is False
    assert result.error is not None
    error_lower = result.error.lower()
    assert "protected" in error_lower or "built-in" in error_lower or "builtin" in error_lower


# ---------------------------------------------------------------------------
# Oversized file rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_rejects_oversized(installer_setup, tmp_path):
    """Install a file larger than max_skill_size should fail with 'size' in error."""
    installer, user_dir, registry = installer_setup

    # Build content that is valid structurally but too large (9 KB+)
    padding = "x" * 9500
    content = dedent(f"""\
        ---
        name: big-skill
        description: A skill that is too large
        load: on_demand
        ---

        # Big Skill

        {padding}
    """)

    skill_file = tmp_path / "big-skill.md"
    skill_file.write_text(content, encoding="utf-8")

    result = await installer.install_from_local(skill_file)

    assert result.success is False
    assert result.error is not None
    assert "size" in result.error.lower()


# ---------------------------------------------------------------------------
# Invalid format rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_rejects_invalid_format(installer_setup, tmp_path):
    """Install a file without front-matter should fail."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "bad-skill.md"
    skill_file.write_text(_INVALID_SKILL_NO_FRONTMATTER, encoding="utf-8")

    result = await installer.install_from_local(skill_file)

    assert result.success is False
    assert result.error is not None
    assert len(result.error) > 0


# ---------------------------------------------------------------------------
# Duplicate without force
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_rejects_duplicate_without_force(installer_setup, tmp_path):
    """Installing the same skill twice without force=True should fail on second."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(_VALID_SKILL_CONTENT, encoding="utf-8")

    first = await installer.install_from_local(skill_file)
    assert first.success is True

    second = await installer.install_from_local(skill_file)
    assert second.success is False
    assert second.error is not None
    assert "exists" in second.error.lower() or "duplicate" in second.error.lower()


# ---------------------------------------------------------------------------
# Duplicate with force
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_allows_duplicate_with_force(installer_setup, tmp_path):
    """Installing the same skill twice with force=True should succeed on second."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(_VALID_SKILL_CONTENT, encoding="utf-8")

    first = await installer.install_from_local(skill_file)
    assert first.success is True

    second = await installer.install_from_local(skill_file, force=True)
    assert second.success is True
    assert second.name == "my-skill"


# ---------------------------------------------------------------------------
# Remove user skill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_user_skill(installer_setup, tmp_path):
    """Install then remove: file gone, registry no longer has the skill."""
    installer, user_dir, registry = installer_setup

    skill_file = tmp_path / "my-skill.md"
    skill_file.write_text(_VALID_SKILL_CONTENT, encoding="utf-8")

    install_result = await installer.install_from_local(skill_file)
    assert install_result.success is True
    assert registry.get("my-skill") is not None

    remove_result = installer.remove("my-skill")

    assert remove_result.success is True
    assert not (user_dir / "my-skill.md").exists()
    assert registry.get("my-skill") is None


# ---------------------------------------------------------------------------
# Remove builtin rejected
# ---------------------------------------------------------------------------

def test_remove_builtin_rejected(installer_setup):
    """Trying to remove a built-in skill should fail."""
    installer, user_dir, registry = installer_setup

    result = installer.remove("translate")

    assert result.success is False
    assert result.error is not None
    error_lower = result.error.lower()
    assert "built-in" in error_lower or "builtin" in error_lower or "protected" in error_lower


# ---------------------------------------------------------------------------
# Remove nonexistent
# ---------------------------------------------------------------------------

def test_remove_nonexistent(installer_setup):
    """Removing an unknown skill should fail gracefully."""
    installer, user_dir, registry = installer_setup

    result = installer.remove("no-such-skill")

    assert result.success is False
    assert result.error is not None
    assert len(result.error) > 0


# ---------------------------------------------------------------------------
# Remote always → on_demand downgrade
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_install_forces_on_demand_for_remote_always(installer_setup):
    """install_from_bytes with is_remote=True and load:always → stored as on_demand."""
    installer, user_dir, registry = installer_setup

    content_bytes = _ALWAYS_SKILL_CONTENT.encode("utf-8")

    result = await installer.install_from_bytes(
        content_bytes=content_bytes,
        source="https://example.com/always-skill.md",
        is_remote=True,
        force=False,
    )

    assert result.success is True
    skill_file = user_dir / "always-skill.md"
    assert skill_file.exists()
    written = skill_file.read_text(encoding="utf-8")
    assert "load: on_demand" in written
    assert "load: always" not in written
