# input: mindclaw.orchestrator.cron_scheduler, mindclaw.orchestrator.cron_store
# output: CronScheduler 后台调度测试
# pos: 验证 cron 调度器的启动、触发和停止
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
from datetime import datetime
from pathlib import Path

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


def _create_task_file(data_dir: Path, tasks: dict) -> None:
    (data_dir / "cron_tasks.json").write_text(json.dumps(tasks), encoding="utf-8")


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops(store):
    """CronScheduler should start a background task and stop cleanly."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []
    scheduler = CronScheduler(
        store=store,
        on_trigger=lambda task_id, task: triggered.append((task_id, task)),
    )

    await scheduler.start()
    assert scheduler.is_running

    await scheduler.stop()
    assert not scheduler.is_running


@pytest.mark.asyncio
async def test_scheduler_triggers_due_task(store, data_dir):
    """CronScheduler should trigger tasks that are due."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(task_id, task):
        triggered.append((task_id, task["name"]))

    # Create a task with "every minute" schedule, created in the past so it's due
    _create_task_file(data_dir, {
        "cron_test": {
            "name": "every-minute",
            "cron_expr": "* * * * *",
            "action": "Ping",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        }
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
        check_interval=0.1,
    )

    await scheduler.start()
    await scheduler.check_once()
    await scheduler.stop()

    assert len(triggered) == 1
    assert triggered[0] == ("cron_test", "every-minute")


@pytest.mark.asyncio
async def test_scheduler_empty_tasks(store):
    """CronScheduler should handle empty task file gracefully."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    scheduler = CronScheduler(
        store=store,
        on_trigger=lambda task_id, task: None,
    )

    await scheduler.start()
    await scheduler.check_once()
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_updates_last_run(store, data_dir):
    """CronScheduler should update last_run after triggering a task."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    async def on_trigger(task_id, task):
        pass

    _create_task_file(data_dir, {
        "cron_lr": {
            "name": "track-run",
            "cron_expr": "* * * * *",
            "action": "Track",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        }
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
        check_interval=0.1,
    )

    await scheduler.start()
    await scheduler.check_once()
    await scheduler.stop()

    # Verify last_run was updated
    task = await store.get("cron_lr")
    assert task is not None
    assert task["last_run"] is not None
    assert task["last_run"] != "2020-01-01T00:00:00"


@pytest.mark.asyncio
async def test_new_task_does_not_fire_immediately(store, data_dir):
    """A newly created task should NOT fire immediately."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(task_id, task):
        triggered.append(task["name"])

    _create_task_file(data_dir, {
        "cron_new": {
            "name": "daily-3am",
            "cron_expr": "0 3 * * *",
            "action": "Run daily",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "enabled": True,
        }
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
    )

    await scheduler.check_once()
    assert len(triggered) == 0


@pytest.mark.asyncio
async def test_failed_callback_does_not_update_last_run(store, data_dir):
    """If on_trigger callback fails, last_run should NOT be updated."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    async def failing_trigger(task_id, task):
        raise RuntimeError("Callback failed!")

    _create_task_file(data_dir, {
        "cron_fail": {
            "name": "will-fail",
            "cron_expr": "* * * * *",
            "action": "Fail",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        }
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=failing_trigger,
    )

    await scheduler.check_once()

    task = await store.get("cron_fail")
    assert task is not None
    assert task["last_run"] == "2020-01-01T00:00:00"


@pytest.mark.asyncio
async def test_concurrent_task_file_access(store, data_dir):
    """Concurrent check_once calls should not corrupt cron_tasks.json."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(task_id, task):
        triggered.append(task["name"])
        await asyncio.sleep(0.01)

    _create_task_file(data_dir, {
        "cron_a": {
            "name": "task-a",
            "cron_expr": "* * * * *",
            "action": "A",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        },
        "cron_b": {
            "name": "task-b",
            "cron_expr": "* * * * *",
            "action": "B",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        },
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
    )

    await asyncio.gather(
        scheduler.check_once(),
        scheduler.check_once(),
    )

    tasks = await store.load()
    assert "cron_a" in tasks
    assert "cron_b" in tasks


@pytest.mark.asyncio
async def test_disabled_task_not_triggered(store, data_dir):
    """Disabled tasks should be skipped."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    triggered = []

    async def on_trigger(task_id, task):
        triggered.append(task["name"])

    _create_task_file(data_dir, {
        "cron_off": {
            "name": "disabled-task",
            "cron_expr": "* * * * *",
            "action": "Skip me",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": False,
        }
    })

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
    )

    await scheduler.check_once()
    assert len(triggered) == 0
