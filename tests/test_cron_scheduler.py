# input: mindclaw.orchestrator.cron_scheduler
# output: CronScheduler 后台调度测试
# pos: 验证 cron 调度器的启动、触发和停止
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


def _create_task_file(data_dir: Path, tasks: dict) -> None:
    (data_dir / "cron_tasks.json").write_text(json.dumps(tasks), encoding="utf-8")


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops(data_dir):
    """CronScheduler should start a background task and stop cleanly."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []
    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=lambda name, action: triggered.append((name, action)),
    )

    await scheduler.start()
    assert scheduler.is_running

    await scheduler.stop()
    assert not scheduler.is_running


@pytest.mark.asyncio
async def test_scheduler_loads_tasks_from_file(data_dir):
    """CronScheduler should load tasks from cron_tasks.json on start."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    _create_task_file(data_dir, {
        "cron_abc": {
            "name": "test-task",
            "cron_expr": "* * * * *",
            "action": "Say hello",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
        }
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=lambda name, action: None,
    )

    await scheduler.start()
    assert scheduler.task_count == 1
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_triggers_due_task(data_dir):
    """CronScheduler should trigger tasks that are due."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(name, action):
        triggered.append((name, action))

    # Create a task with "every minute" schedule, created in the past so it's due
    _create_task_file(data_dir, {
        "cron_test": {
            "name": "every-minute",
            "cron_expr": "* * * * *",
            "action": "Ping",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
        }
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=on_trigger,
        check_interval=0.1,  # Check every 0.1s for test speed
    )

    await scheduler.start()
    # Force a check cycle
    await scheduler.check_once()
    await scheduler.stop()

    assert len(triggered) == 1
    assert triggered[0] == ("every-minute", "Ping")


@pytest.mark.asyncio
async def test_scheduler_empty_tasks(data_dir):
    """CronScheduler should handle empty task file gracefully."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=lambda name, action: None,
    )

    await scheduler.start()
    await scheduler.check_once()
    await scheduler.stop()

    # No crash = pass


@pytest.mark.asyncio
async def test_scheduler_updates_last_run(data_dir):
    """CronScheduler should update last_run after triggering a task."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    async def on_trigger(name, action):
        pass

    _create_task_file(data_dir, {
        "cron_lr": {
            "name": "track-run",
            "cron_expr": "* * * * *",
            "action": "Track",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
        }
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=on_trigger,
        check_interval=0.1,
    )

    await scheduler.start()
    await scheduler.check_once()
    await scheduler.stop()

    # Verify last_run was updated in file
    tasks = json.loads((data_dir / "cron_tasks.json").read_text())
    assert tasks["cron_lr"]["last_run"] is not None


@pytest.mark.asyncio
async def test_new_task_does_not_fire_immediately(data_dir):
    """BUG FIX: A newly created task should NOT fire immediately.

    It should wait until its next cron time after created_at.
    """
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(name, action):
        triggered.append(name)

    # Task created "now" with daily schedule (0 3 * * * = 3 AM)
    _create_task_file(data_dir, {
        "cron_new": {
            "name": "daily-3am",
            "cron_expr": "0 3 * * *",
            "action": "Run daily",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
        }
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=on_trigger,
    )

    await scheduler.check_once()
    # Task should NOT have fired — next 3 AM is in the future
    assert len(triggered) == 0


@pytest.mark.asyncio
async def test_failed_callback_does_not_update_last_run(data_dir):
    """BUG FIX: If on_trigger callback fails, last_run should NOT be updated."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    async def failing_trigger(name, action):
        raise RuntimeError("Callback failed!")

    # Task with last_run far in the past so it's due
    _create_task_file(data_dir, {
        "cron_fail": {
            "name": "will-fail",
            "cron_expr": "* * * * *",
            "action": "Fail",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
        }
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=failing_trigger,
    )

    await scheduler.check_once()

    tasks = json.loads((data_dir / "cron_tasks.json").read_text())
    # last_run should still be the original value — NOT updated
    assert tasks["cron_fail"]["last_run"] == "2020-01-01T00:00:00"


@pytest.mark.asyncio
async def test_concurrent_task_file_access(data_dir):
    """IMPROVEMENT: Concurrent check_once calls should not corrupt cron_tasks.json."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(name, action):
        triggered.append(name)
        await asyncio.sleep(0.01)  # Simulate async work

    # Create two tasks, both due
    _create_task_file(data_dir, {
        "cron_a": {
            "name": "task-a",
            "cron_expr": "* * * * *",
            "action": "A",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
        },
        "cron_b": {
            "name": "task-b",
            "cron_expr": "* * * * *",
            "action": "B",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
        },
    })

    scheduler = CronScheduler(
        data_dir=data_dir,
        on_trigger=on_trigger,
    )

    # Run two check_once concurrently
    await asyncio.gather(
        scheduler.check_once(),
        scheduler.check_once(),
    )

    # File should still be valid JSON
    tasks = json.loads((data_dir / "cron_tasks.json").read_text())
    assert "cron_a" in tasks
    assert "cron_b" in tasks
