# input: mindclaw.orchestrator.context, mindclaw.orchestrator.cron_context
# output: Cron 系统提示构建测试
# pos: 验证 ContextBuilder.build_cron_system_prompt 注入工具限制
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


# ── build_cron_system_prompt ──────────────────────────────────


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

    assert "scheduled" in prompt.lower() or "unattended" in prompt.lower()
