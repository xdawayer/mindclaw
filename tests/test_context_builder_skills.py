# input: mindclaw.orchestrator.context, mindclaw.skills.registry
# output: ContextBuilder 技能注入测试
# pos: 验证系统提示中正确注入技能摘要和 always 技能内容
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def skills_dir(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()

    (d / "summarize.md").write_text(dedent("""\
        ---
        name: summarize-article
        description: Summarize article key points
        load: on_demand
        ---

        # Summarize Article
        Use web_fetch to get content, then summarize.
    """))

    (d / "translate.md").write_text(dedent("""\
        ---
        name: translate
        description: Translate text
        load: always
        ---

        # Translate
        Detect source language and translate.
    """))

    return d


@pytest.fixture
def memory_manager():
    mm = MagicMock()
    mm.load_memory.return_value = ""
    return mm


def test_system_prompt_includes_skill_summaries(memory_manager, skills_dir):
    """System prompt should include skill name + description summaries."""
    from mindclaw.orchestrator.context import ContextBuilder
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    builder = ContextBuilder(memory_manager=memory_manager, skill_registry=registry)
    prompt = builder.build_system_prompt()

    assert "## Available Skills" in prompt
    assert "summarize-article" in prompt
    assert "translate" in prompt


def test_system_prompt_includes_always_skill_content(memory_manager, skills_dir):
    """System prompt should include full content of 'always' skills."""
    from mindclaw.orchestrator.context import ContextBuilder
    from mindclaw.skills.registry import SkillRegistry

    registry = SkillRegistry(skills_dir)
    builder = ContextBuilder(memory_manager=memory_manager, skill_registry=registry)
    prompt = builder.build_system_prompt()

    # 'always' skill content should be included
    assert "Detect source language and translate" in prompt


def test_system_prompt_without_skill_registry(memory_manager):
    """ContextBuilder should work without a skill registry (backward compat)."""
    from mindclaw.orchestrator.context import ContextBuilder

    builder = ContextBuilder(memory_manager=memory_manager)
    prompt = builder.build_system_prompt()

    assert "MindClaw" in prompt
    assert "Available Skills" not in prompt
