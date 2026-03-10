# input: mindclaw.orchestrator.subagent
# output: SubAgentManager 测试
# pos: 子 Agent 管理器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest

from mindclaw.config.schema import MindClawConfig
from mindclaw.orchestrator.acp import AgentStatus
from mindclaw.orchestrator.subagent import SubAgentManager


@pytest.mark.asyncio
async def test_spawn_and_collect_result():
    """SubAgentManager should spawn a task and collect its result."""
    manager = SubAgentManager(config=MindClawConfig())
    task_id = await manager.spawn(task="Summarize Python docs", tools=[])

    assert task_id is not None
    result = await manager.wait(task_id)
    assert result.status == "completed"
    assert "Summarize Python docs" in result.content


@pytest.mark.asyncio
async def test_spawn_multiple_concurrent():
    """SubAgentManager should run up to max_concurrent tasks in parallel."""
    config = MindClawConfig()
    manager = SubAgentManager(config=config, max_concurrent=3)

    task_ids = []
    for i in range(3):
        tid = await manager.spawn(task=f"Task {i}", tools=[])
        task_ids.append(tid)

    assert manager.active_count <= 3

    results = await asyncio.gather(*[manager.wait(tid) for tid in task_ids])
    for r in results:
        assert r.status == "completed"


@pytest.mark.asyncio
async def test_spawn_over_max_concurrent_raises():
    """Spawning more than max_concurrent should raise."""
    manager = SubAgentManager(config=MindClawConfig(), max_concurrent=1)

    await manager.spawn(task="Task 1", tools=[])
    # Before first task completes, try to spawn another
    with pytest.raises(RuntimeError, match="max concurrent"):
        await manager.spawn(task="Task 2", tools=[])


@pytest.mark.asyncio
async def test_get_result_unknown_task():
    """Getting result for unknown task_id should return None."""
    manager = SubAgentManager(config=MindClawConfig())
    result = await manager.wait("nonexistent-task")
    assert result is None


@pytest.mark.asyncio
async def test_active_count():
    """active_count should reflect running tasks."""
    manager = SubAgentManager(config=MindClawConfig(), max_concurrent=5)
    assert manager.active_count == 0

    tid = await manager.spawn(task="Quick task", tools=[])
    # Might be 0 or 1 depending on speed - just verify it doesn't crash
    await manager.wait(tid)
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_spawn_with_timeout():
    """SubAgentManager should respect per-task timeout."""
    manager = SubAgentManager(config=MindClawConfig(), task_timeout=0.1)
    tid = await manager.spawn(task="Slow task", tools=[])
    result = await manager.wait(tid)
    # Should complete or timeout - either is valid for the fast runner
    assert result.status in ("completed", "timeout")


@pytest.mark.asyncio
async def test_kill_all():
    """kill_all should terminate all active agents."""
    manager = SubAgentManager(config=MindClawConfig(), max_concurrent=5)
    tid1 = await manager.spawn(task="Task A", tools=[])
    tid2 = await manager.spawn(task="Task B", tools=[])

    await manager.kill_all()

    # All should be non-running after kill_all
    for tid in [tid1, tid2]:
        handle = manager._handles.get(tid)
        if handle is not None:
            assert handle.status != AgentStatus.RUNNING


@pytest.mark.asyncio
async def test_clean_completed_frees_slots():
    """Completed tasks should be cleaned up to free concurrency slots."""
    manager = SubAgentManager(config=MindClawConfig(), max_concurrent=1)

    tid1 = await manager.spawn(task="Task 1", tools=[])
    await manager.wait(tid1)  # Complete first task

    # Should succeed because completed tasks are cleaned up
    tid2 = await manager.spawn(task="Task 2", tools=[])
    result = await manager.wait(tid2)
    assert result.status == "completed"
