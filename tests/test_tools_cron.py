# input: mindclaw.tools.cron, mindclaw.orchestrator.cron_store
# output: Cron 工具 (add/list/remove/toggle) 测试
# pos: 验证定时任务工具的 CRUD 操作和持久化
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.orchestrator.cron_store import CronTaskStore


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def store(data_dir):
    return CronTaskStore(data_dir=data_dir)


@pytest.mark.asyncio
async def test_cron_add_creates_task(store, data_dir):
    """cron_add should create a task and persist it."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(store=store)
    result = await tool.execute({
        "name": "daily-backup",
        "cron_expr": "0 22 * * *",
        "action": "Back up MEMORY.md",
    })

    assert "daily-backup" in result
    assert "added" in result.lower()

    tasks = await store.load()
    assert len(tasks) == 1
    task = list(tasks.values())[0]
    assert task["name"] == "daily-backup"
    assert task["cron_expr"] == "0 22 * * *"
    assert task["enabled"] is True


@pytest.mark.asyncio
async def test_cron_add_validates_expression(store):
    """cron_add should reject invalid cron expressions."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(store=store)
    result = await tool.execute({
        "name": "bad-task",
        "cron_expr": "not a valid cron",
        "action": "Do something",
    })

    assert "invalid" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_cron_add_with_notify_fields(store):
    """cron_add should store notify_channel and notify_chat_id."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(store=store)
    await tool.execute({
        "name": "notify-task",
        "cron_expr": "0 8 * * *",
        "action": "Morning",
        "notify_channel": "telegram",
        "notify_chat_id": "12345",
        "max_iterations": 20,
        "timeout": 600,
    })

    tasks = await store.load()
    task = list(tasks.values())[0]
    assert task["notify_channel"] == "telegram"
    assert task["notify_chat_id"] == "12345"
    assert task["max_iterations"] == 20
    assert task["timeout"] == 600


@pytest.mark.asyncio
async def test_cron_list_shows_tasks(store):
    """cron_list should show all scheduled tasks."""
    from mindclaw.tools.cron import CronAddTool, CronListTool

    add_tool = CronAddTool(store=store)
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

    list_tool = CronListTool(store=store)
    result = await list_tool.execute({})

    assert "task-a" in result
    assert "task-b" in result
    assert "0 8 * * *" in result
    assert "*/30 * * * *" in result


@pytest.mark.asyncio
async def test_cron_list_empty(store):
    """cron_list should indicate no tasks when empty."""
    from mindclaw.tools.cron import CronListTool

    tool = CronListTool(store=store)
    result = await tool.execute({})

    assert "no" in result.lower()


@pytest.mark.asyncio
async def test_cron_remove_deletes_task(store):
    """cron_remove should delete a task by ID."""
    from mindclaw.tools.cron import CronAddTool, CronRemoveTool

    add_tool = CronAddTool(store=store)
    await add_tool.execute({
        "name": "to-delete",
        "cron_expr": "0 12 * * *",
        "action": "Noon reminder",
    })

    tasks = await store.load()
    task_id = list(tasks.keys())[0]

    remove_tool = CronRemoveTool(store=store)
    result = await remove_tool.execute({"task_id": task_id})

    assert "removed" in result.lower()

    tasks = await store.load()
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_cron_remove_nonexistent(store):
    """cron_remove should handle nonexistent task ID gracefully."""
    from mindclaw.tools.cron import CronRemoveTool

    tool = CronRemoveTool(store=store)
    result = await tool.execute({"task_id": "nonexistent-id"})

    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_cron_add_duplicate_name(store):
    """cron_add should reject duplicate task names."""
    from mindclaw.tools.cron import CronAddTool

    tool = CronAddTool(store=store)
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

    assert "exists" in result.lower()


@pytest.mark.asyncio
async def test_cron_toggle_enables_disables(store):
    """cron_toggle should enable/disable tasks."""
    from mindclaw.tools.cron import CronAddTool, CronToggleTool

    add_tool = CronAddTool(store=store)
    await add_tool.execute({
        "name": "toggle-me",
        "cron_expr": "0 8 * * *",
        "action": "Test",
    })

    tasks = await store.load()
    task_id = list(tasks.keys())[0]

    toggle_tool = CronToggleTool(store=store)

    result = await toggle_tool.execute({"task_id": task_id, "enabled": False})
    assert "disabled" in result.lower()

    task = await store.get(task_id)
    assert task is not None
    assert task["enabled"] is False

    result = await toggle_tool.execute({"task_id": task_id, "enabled": True})
    assert "enabled" in result.lower()


@pytest.mark.asyncio
async def test_cron_toggle_nonexistent(store):
    """cron_toggle should handle nonexistent task ID."""
    from mindclaw.tools.cron import CronToggleTool

    tool = CronToggleTool(store=store)
    result = await tool.execute({"task_id": "nope", "enabled": False})

    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_cron_tools_risk_level(store):
    """Cron tools should have correct risk levels."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.cron import CronAddTool, CronListTool, CronRemoveTool, CronToggleTool

    assert CronAddTool(store=store).risk_level == RiskLevel.MODERATE
    assert CronListTool(store=store).risk_level == RiskLevel.SAFE
    assert CronRemoveTool(store=store).risk_level == RiskLevel.MODERATE
    assert CronToggleTool(store=store).risk_level == RiskLevel.MODERATE
