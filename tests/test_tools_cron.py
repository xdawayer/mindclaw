# input: mindclaw.tools.cron
# output: Cron 工具 (add/list/remove) 测试
# pos: 验证定时任务工具的 CRUD 操作和持久化
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.mark.asyncio
async def test_cron_add_creates_task(data_dir):
    """cron_add should create a task and persist it."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(data_dir=data_dir)
    result = await tool.execute({
        "name": "daily-backup",
        "cron_expr": "0 22 * * *",
        "action": "Back up MEMORY.md",
    })

    assert "daily-backup" in result
    assert "created" in result.lower() or "added" in result.lower()

    # Check persistence
    tasks_file = data_dir / "cron_tasks.json"
    assert tasks_file.exists()
    tasks = json.loads(tasks_file.read_text())
    assert len(tasks) == 1
    task = list(tasks.values())[0]
    assert task["name"] == "daily-backup"
    assert task["cron_expr"] == "0 22 * * *"


@pytest.mark.asyncio
async def test_cron_add_validates_expression(data_dir):
    """cron_add should reject invalid cron expressions."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(data_dir=data_dir)
    result = await tool.execute({
        "name": "bad-task",
        "cron_expr": "not a valid cron",
        "action": "Do something",
    })

    assert "invalid" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_cron_list_shows_tasks(data_dir):
    """cron_list should show all scheduled tasks."""
    from mindclaw.tools.cron import CronAddTool, CronListTool

    add_tool = CronAddTool(data_dir=data_dir)
    await add_tool.execute({
        "name": "task-a",
        "cron_expr": "0 8 * * *",
        "action": "Morning greeting",
    })
    await add_tool.execute({
        "name": "task-b",
        "cron_expr": "*/30 * * * *",
        "action": "Check email",
    })

    list_tool = CronListTool(data_dir=data_dir)
    result = await list_tool.execute({})

    assert "task-a" in result
    assert "task-b" in result
    assert "0 8 * * *" in result
    assert "*/30 * * * *" in result


@pytest.mark.asyncio
async def test_cron_list_empty(data_dir):
    """cron_list should indicate no tasks when empty."""
    from mindclaw.tools.cron import CronListTool

    tool = CronListTool(data_dir=data_dir)
    result = await tool.execute({})

    assert "no" in result.lower() or "empty" in result.lower()


@pytest.mark.asyncio
async def test_cron_remove_deletes_task(data_dir):
    """cron_remove should delete a task by ID."""
    from mindclaw.tools.cron import CronAddTool, CronListTool, CronRemoveTool

    add_tool = CronAddTool(data_dir=data_dir)
    result = await add_tool.execute({
        "name": "to-delete",
        "cron_expr": "0 12 * * *",
        "action": "Noon reminder",
    })

    # Extract task_id from result
    tasks = json.loads((data_dir / "cron_tasks.json").read_text())
    task_id = list(tasks.keys())[0]

    remove_tool = CronRemoveTool(data_dir=data_dir)
    result = await remove_tool.execute({"task_id": task_id})

    assert "removed" in result.lower() or "deleted" in result.lower()

    # Verify persistence
    tasks = json.loads((data_dir / "cron_tasks.json").read_text())
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_cron_remove_nonexistent(data_dir):
    """cron_remove should handle nonexistent task ID gracefully."""
    from mindclaw.tools.cron import CronRemoveTool

    tool = CronRemoveTool(data_dir=data_dir)
    result = await tool.execute({"task_id": "nonexistent-id"})

    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_cron_add_duplicate_name(data_dir):
    """cron_add should reject duplicate task names."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(data_dir=data_dir)
    await tool.execute({
        "name": "dup-task",
        "cron_expr": "0 8 * * *",
        "action": "Morning",
    })

    result = await tool.execute({
        "name": "dup-task",
        "cron_expr": "0 22 * * *",
        "action": "Evening",
    })

    assert "exists" in result.lower() or "duplicate" in result.lower()


@pytest.mark.asyncio
async def test_cron_tools_risk_level():
    """Cron tools should be MODERATE risk level."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.cron import CronAddTool, CronListTool, CronRemoveTool

    # data_dir doesn't matter for risk level check
    assert CronAddTool(data_dir=Path("/tmp")).risk_level == RiskLevel.MODERATE
    assert CronListTool(data_dir=Path("/tmp")).risk_level == RiskLevel.SAFE
    assert CronRemoveTool(data_dir=Path("/tmp")).risk_level == RiskLevel.MODERATE
