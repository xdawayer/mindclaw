# input: mindclaw.orchestrator.context, mindclaw.orchestrator.cron_context
# output: Cron 系统提示构建测试
# pos: 验证 ContextBuilder.build_cron_system_prompt 注入工具限制、输出规则、质量标准
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import MagicMock

import pytest

from mindclaw.orchestrator.cron_context import CronExecutionConstraints


@pytest.fixture
def context_builder():
    from mindclaw.knowledge.memory import MemoryManager
    from mindclaw.orchestrator.context import ContextBuilder

    mm = MagicMock(spec=MemoryManager)
    mm.load_memory.return_value = ""
    return ContextBuilder(memory_manager=mm)


# -- Constraints injection --


def test_cron_prompt_includes_tool_restrictions(context_builder):
    """Cron system prompt should warn about blocked tools."""
    constraints = CronExecutionConstraints(
        blocked_tools=frozenset({"exec", "spawn_task"}),
    )
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "exec" in prompt
    assert "spawn_task" in prompt


def test_cron_prompt_includes_iteration_limit(context_builder):
    """Cron system prompt should state the max iteration count."""
    constraints = CronExecutionConstraints(max_iterations=10)
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "10" in prompt


def test_cron_prompt_includes_timeout(context_builder):
    """Cron system prompt should state the timeout."""
    constraints = CronExecutionConstraints(timeout_seconds=120)
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "120" in prompt


def test_cron_prompt_includes_base_prompt(context_builder):
    """Cron system prompt should include the base MindClaw prompt."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "MindClaw" in prompt


def test_cron_prompt_marks_unattended(context_builder):
    """Cron system prompt should indicate this is an unattended/scheduled task."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "scheduled" in prompt.lower()
    assert "unattended" in prompt.lower()


# -- Output rules --


def test_cron_prompt_enforces_chinese_output(context_builder):
    """Cron system prompt should mandate Chinese output."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "中文" in prompt


def test_cron_prompt_enforces_markdown_format(context_builder):
    """Cron system prompt should instruct Markdown formatting."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "Markdown" in prompt


def test_cron_prompt_enforces_telegram_length_limit(context_builder):
    """Cron system prompt should warn about Telegram character limit."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "3500" in prompt
    assert "Telegram" in prompt


# -- Data collection strategy --


def test_cron_prompt_includes_data_collection_strategy(context_builder):
    """Cron system prompt should advise on tool usage for data collection."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "### Data Collection" in prompt
    assert "web_search" in prompt
    assert "web_fetch" in prompt
    assert "read_file" in prompt
    assert "memory_search" in prompt


# -- Quality bar --


def test_cron_prompt_includes_quality_standards(context_builder):
    """Cron system prompt should set quality expectations."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "Deduplicate" in prompt or "deduplicate" in prompt.lower()
    assert "Action Required" in prompt


def test_cron_prompt_requires_structured_sections(context_builder):
    """Cron system prompt should require structured output with sections."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    assert "### Output Rules" in prompt
    assert "section headers" in prompt.lower() or "headings" in prompt.lower()
    assert "Lead with the most important" in prompt


# -- Forward-looking ending --


def test_cron_prompt_requires_forward_looking_ending(context_builder):
    """Cron system prompt should require a forward-looking ending section."""
    constraints = CronExecutionConstraints()
    prompt = context_builder.build_cron_system_prompt(constraints)

    # Should mention at least one of these ending patterns
    has_ending_guidance = (
        "下期关注" in prompt
        or "行动建议" in prompt
        or "明日预告" in prompt
    )
    assert has_ending_guidance, (
        "Cron prompt should guide agent to end with a forward-looking section"
    )
