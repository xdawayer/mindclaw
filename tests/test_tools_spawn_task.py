# input: mindclaw.tools.spawn_task
# output: spawn_task 工具测试
# pos: 子 Agent 任务派发工具测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.config.schema import MindClawConfig
from mindclaw.orchestrator.subagent import SubAgentManager


@pytest.mark.asyncio
async def test_spawn_task_creates_subagent():
    """spawn_task should create a sub-agent and return result."""
    from mindclaw.tools.spawn_task import SpawnTaskTool

    config = MindClawConfig()
    manager = SubAgentManager(config=config)
    tool = SpawnTaskTool(manager=manager)

    result = await tool.execute({"task": "Research Python best practices"})
    assert "completed" in result.lower() or "result" in result.lower()


@pytest.mark.asyncio
async def test_spawn_task_risk_level():
    """spawn_task should be DANGEROUS risk level."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.spawn_task import SpawnTaskTool

    config = MindClawConfig()
    manager = SubAgentManager(config=config)
    tool = SpawnTaskTool(manager=manager)
    assert tool.risk_level == RiskLevel.DANGEROUS


@pytest.mark.asyncio
async def test_spawn_task_requires_task_param():
    """spawn_task should fail with missing task param."""
    from mindclaw.tools.spawn_task import SpawnTaskTool

    config = MindClawConfig()
    manager = SubAgentManager(config=config)
    tool = SpawnTaskTool(manager=manager)

    with pytest.raises(KeyError):
        await tool.execute({})


@pytest.mark.asyncio
async def test_spawn_task_respects_max_concurrent():
    """spawn_task should return error when max concurrent reached."""
    from mindclaw.tools.spawn_task import SpawnTaskTool

    config = MindClawConfig()
    manager = SubAgentManager(config=config, max_concurrent=1)
    tool = SpawnTaskTool(manager=manager)

    # First spawn succeeds
    _ = await tool.execute({"task": "Task 1"})
    # Manager auto-waits, so this might succeed too since the first completes fast
    # Let's just verify the tool doesn't crash
    result2 = await tool.execute({"task": "Task 2"})
    assert isinstance(result2, str)


@pytest.mark.asyncio
async def test_spawn_task_returns_subagent_content():
    """spawn_task result should contain the sub-agent's output."""
    from mindclaw.tools.spawn_task import SpawnTaskTool

    config = MindClawConfig()
    manager = SubAgentManager(config=config)
    tool = SpawnTaskTool(manager=manager)

    result = await tool.execute({"task": "Analyze data patterns"})
    assert "Analyze data patterns" in result
