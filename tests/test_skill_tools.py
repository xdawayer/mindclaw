# input: mindclaw.tools.skill_tools, mindclaw.skills.registry, mindclaw.skills.installer
# output: LLM 技能工具测试
# pos: 验证 skill_search/list/show/install/remove 工具的风险等级和执行行为
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from textwrap import dedent

import pytest

from mindclaw.tools.base import RiskLevel


@pytest.fixture
def tool_setup(tmp_path):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Built-in translate
        load: always
        ---

        # Translate
    """))

    user = tmp_path / "user"
    user.mkdir()

    from mindclaw.skills.installer import SkillInstaller
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry([builtin, user])
    installer = SkillInstaller(
        user_skills_dir=user,
        registry=registry,
        index_client=None,
        max_skill_size=8192,
    )
    return registry, installer


def test_skill_list_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillListTool

    registry, installer = tool_setup
    tool = SkillListTool(registry=registry)
    assert tool.risk_level == RiskLevel.SAFE


def test_skill_search_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillSearchTool

    tool = SkillSearchTool(index_client=None)
    assert tool.risk_level == RiskLevel.MODERATE


def test_skill_install_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillInstallTool

    registry, installer = tool_setup
    tool = SkillInstallTool(installer=installer, registry=registry)
    assert tool.risk_level == RiskLevel.DANGEROUS


def test_skill_remove_tool_risk_level(tool_setup):
    from mindclaw.tools.skill_tools import SkillRemoveTool

    registry, installer = tool_setup
    tool = SkillRemoveTool(installer=installer)
    assert tool.risk_level == RiskLevel.DANGEROUS


@pytest.mark.asyncio
async def test_skill_list_tool_execute(tool_setup):
    from mindclaw.tools.skill_tools import SkillListTool

    registry, installer = tool_setup
    tool = SkillListTool(registry=registry)
    result = await tool.execute({})
    assert "translate" in result
    assert "builtin" in result


@pytest.mark.asyncio
async def test_skill_show_tool_execute(tool_setup):
    from mindclaw.tools.skill_tools import SkillShowTool

    registry, installer = tool_setup
    tool = SkillShowTool(registry=registry)
    result = await tool.execute({"name": "translate"})
    assert "translate" in result.lower()


@pytest.mark.asyncio
async def test_skill_show_tool_unknown(tool_setup):
    from mindclaw.tools.skill_tools import SkillShowTool

    registry, installer = tool_setup
    tool = SkillShowTool(registry=registry)
    result = await tool.execute({"name": "nonexistent"})
    assert "not found" in result.lower()
