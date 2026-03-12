# input: mindclaw.skills.registry
# output: 技能注册/加载/查询测试
# pos: 验证 SkillRegistry 的 YAML 解析、技能发现和系统提示注入
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from textwrap import dedent

import pytest


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temporary skills directory with sample skill files."""
    d = tmp_path / "skills"
    d.mkdir()

    (d / "summarize.md").write_text(dedent("""\
        ---
        name: summarize-article
        description: Summarize an article's key points
        load: on_demand
        ---

        # Summarize Article

        ## Steps
        1. Use web_fetch to get article content
        2. Extract key points (max 5)
        3. Generate a one-paragraph summary
    """))

    (d / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Translate text to a specified language
        load: always
        ---

        # Translate

        ## Steps
        1. Detect source language
        2. Translate to target language
        3. Keep formatting intact
    """))

    return d


@pytest.fixture
def empty_skills_dir(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    return d


def test_registry_discovers_skills(skills_dir):
    """SkillRegistry should discover all .md files with valid YAML front-matter."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)

    assert len(registry.skills) == 2
    names = {s.name for s in registry.skills}
    assert names == {"summarize-article", "translate"}


def test_registry_parses_metadata(skills_dir):
    """SkillRegistry should parse name, description, and load mode."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)

    summarize = registry.get("summarize-article")
    assert summarize is not None
    assert summarize.name == "summarize-article"
    assert summarize.description == "Summarize an article's key points"
    assert summarize.load == "on_demand"

    translate = registry.get("translate")
    assert translate is not None
    assert translate.load == "always"


def test_registry_skill_summaries(skills_dir):
    """get_skill_summaries() should return name + description for system prompt injection."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    summaries = registry.get_skill_summaries()

    assert len(summaries) == 2
    assert any("summarize-article" in s and "Summarize" in s for s in summaries)
    assert any("translate" in s and "Translate" in s for s in summaries)


def test_registry_always_skills_content(skills_dir):
    """get_always_skills_content() should return full content of 'always' skills only."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    content = registry.get_always_skills_content()

    assert "Translate" in content
    assert "Detect source language" in content
    # on_demand skill should NOT be in always content
    assert "summarize-article" not in content


def test_registry_empty_directory(empty_skills_dir):
    """SkillRegistry should handle empty skills directory gracefully."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(empty_skills_dir)

    assert len(registry.skills) == 0
    assert registry.get_skill_summaries() == []
    assert registry.get_always_skills_content() == ""


def test_registry_nonexistent_directory(tmp_path):
    """SkillRegistry should handle nonexistent directory gracefully."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(tmp_path / "nonexistent")

    assert len(registry.skills) == 0


def test_registry_ignores_malformed_files(tmp_path):
    """SkillRegistry should skip files without valid YAML front-matter."""
    d = tmp_path / "skills"
    d.mkdir()

    # No front-matter
    (d / "bad.md").write_text("# Just a heading\nNo front-matter here.")

    # Valid file
    (d / "good.md").write_text(dedent("""\
        ---
        name: good-skill
        description: A good skill
        load: on_demand
        ---

        # Good Skill
    """))

    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(d)

    assert len(registry.skills) == 1
    assert registry.skills[0].name == "good-skill"


def test_registry_get_returns_none_for_unknown(skills_dir):
    """get() should return None for unknown skill names."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    assert registry.get("nonexistent") is None


def test_registry_skill_file_path(skills_dir):
    """Each skill should know its file path for read_file loading."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    summarize = registry.get("summarize-article")
    assert summarize is not None
    assert summarize.file_path == skills_dir / "summarize.md"


# ---------------------------------------------------------------------------
# Multi-directory support tests
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_dir_setup(tmp_path):
    """Create 3 tmp dirs simulating builtin / project / user layers."""
    from textwrap import dedent

    builtin_dir = tmp_path / "builtin"
    project_dir = tmp_path / "project"
    user_dir = tmp_path / "user"
    builtin_dir.mkdir()
    project_dir.mkdir()
    user_dir.mkdir()

    # builtin: translate + summarize
    (builtin_dir / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Builtin translate skill
        load: on_demand
        ---

        Builtin translate content.
    """))
    (builtin_dir / "summarize.md").write_text(dedent("""\
        ---
        name: summarize-article
        description: Builtin summarize skill
        load: on_demand
        ---

        Builtin summarize content.
    """))

    # project: empty (no .md files)

    # user: translate with different description (overrides builtin)
    (user_dir / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: User translate skill
        load: on_demand
        ---

        User translate content.
    """))

    return builtin_dir, project_dir, user_dir


def test_multi_dir_discovery(multi_dir_setup):
    """SkillRegistry with multiple dirs discovers skills across all dirs (2 unique skills)."""
    from mindclaw.skills.registry import SkillRegistry

    builtin_dir, project_dir, user_dir = multi_dir_setup
    registry = SkillRegistry([builtin_dir, project_dir, user_dir])

    assert len(registry.skills) == 2
    names = {s.name for s in registry.skills}
    assert names == {"translate", "summarize-article"}


def test_multi_dir_user_overrides_builtin(multi_dir_setup):
    """User-layer skill overrides builtin skill; description reflects user version."""
    from mindclaw.skills.registry import SkillRegistry

    builtin_dir, project_dir, user_dir = multi_dir_setup
    registry = SkillRegistry([builtin_dir, project_dir, user_dir])

    translate = registry.get("translate")
    assert translate is not None
    assert translate.description == "User translate skill"


def test_atomic_reload(multi_dir_setup):
    """After adding a new skill file and calling reload(), the new skill appears."""
    from textwrap import dedent

    from mindclaw.skills.registry import SkillRegistry

    builtin_dir, project_dir, user_dir = multi_dir_setup
    registry = SkillRegistry([builtin_dir, project_dir, user_dir])

    assert registry.get("new-skill") is None

    (user_dir / "new-skill.md").write_text(dedent("""\
        ---
        name: new-skill
        description: A brand new skill
        load: on_demand
        ---

        New skill content.
    """))

    registry.reload()

    skill = registry.get("new-skill")
    assert skill is not None
    assert skill.description == "A brand new skill"


def test_protected_names(multi_dir_setup):
    """First directory's skill names are in registry.protected_names."""
    from mindclaw.skills.registry import SkillRegistry

    builtin_dir, project_dir, user_dir = multi_dir_setup
    registry = SkillRegistry([builtin_dir, project_dir, user_dir])

    assert "translate" in registry.protected_names
    assert "summarize-article" in registry.protected_names


def test_get_skill_source_layer(multi_dir_setup):
    """translate from user has source_layer='user'; summarize from builtin has source_layer='builtin'."""
    from mindclaw.skills.registry import SkillRegistry

    builtin_dir, project_dir, user_dir = multi_dir_setup
    registry = SkillRegistry([builtin_dir, project_dir, user_dir])

    translate = registry.get("translate")
    assert translate is not None
    assert translate.source_layer == "user"

    summarize = registry.get("summarize-article")
    assert summarize is not None
    assert summarize.source_layer == "builtin"


def test_single_path_backward_compat(skills_dir):
    """SkillRegistry(single_path) still works (backward compatibility)."""
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    assert len(registry.skills) == 2


def test_skip_underscore_prefixed_files(tmp_path):
    """Files starting with _ (like _ARCHITECTURE.md) must be skipped."""
    from textwrap import dedent

    from mindclaw.skills.registry import SkillRegistry

    d = tmp_path / "skills"
    d.mkdir()

    (d / "_ARCHITECTURE.md").write_text(dedent("""\
        ---
        name: should-be-skipped
        description: Should not appear
        load: on_demand
        ---

        Architecture doc.
    """))
    (d / "real-skill.md").write_text(dedent("""\
        ---
        name: real-skill
        description: A real skill
        load: on_demand
        ---

        Real skill content.
    """))

    registry = SkillRegistry(d)

    assert registry.get("should-be-skipped") is None
    assert registry.get("real-skill") is not None
    assert len(registry.skills) == 1
