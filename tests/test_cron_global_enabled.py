# input: mindclaw.config.schema, mindclaw.orchestrator.cron_scheduler
# output: Phase 0h 全局 cron 开关测试
# pos: 验证 AgentConfig.cron_enabled 和 scheduler global_enabled_fn
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
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


def _create_due_task(data_dir: Path) -> None:
    tasks = {
        "cron_x": {
            "name": "due-task",
            "cron_expr": "* * * * *",
            "action": "Run",
            "created_at": "2020-01-01T00:00:00",
            "last_run": "2020-01-01T00:00:00",
            "enabled": True,
        }
    }
    (data_dir / "cron_tasks.json").write_text(
        json.dumps(tasks), encoding="utf-8"
    )


# ── Config field ──────────────────────────────────────────────


def test_agent_config_cron_enabled_default():
    """AgentConfig should have cron_enabled=True by default."""
    from mindclaw.config.schema import AgentConfig

    cfg = AgentConfig()
    assert cfg.cron_enabled is True


def test_agent_config_cron_enabled_alias():
    """cron_enabled should accept camelCase alias 'cronEnabled'."""
    from mindclaw.config.schema import AgentConfig

    cfg = AgentConfig(cronEnabled=False)
    assert cfg.cron_enabled is False


# ── Scheduler global_enabled_fn ───────────────────────────────


@pytest.mark.asyncio
async def test_scheduler_skips_all_when_globally_disabled(store, data_dir):
    """When global_enabled_fn returns False, no tasks should trigger."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    _create_due_task(data_dir)
    triggered = []

    scheduler = CronScheduler(
        store=store,
        on_trigger=lambda tid, t: triggered.append(tid),
        global_enabled_fn=lambda: False,
    )

    await scheduler.check_once()
    assert len(triggered) == 0


@pytest.mark.asyncio
async def test_scheduler_runs_when_globally_enabled(store, data_dir):
    """When global_enabled_fn returns True (or None), tasks trigger normally."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    _create_due_task(data_dir)
    triggered = []

    async def on_trigger(tid, t):
        triggered.append(tid)

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
        global_enabled_fn=lambda: True,
    )

    await scheduler.check_once()
    assert len(triggered) == 1


@pytest.mark.asyncio
async def test_scheduler_default_no_global_fn(store, data_dir):
    """When global_enabled_fn is not provided, scheduler runs normally."""
    from mindclaw.orchestrator.cron_scheduler import CronScheduler

    _create_due_task(data_dir)
    triggered = []

    async def on_trigger(tid, t):
        triggered.append(tid)

    scheduler = CronScheduler(
        store=store,
        on_trigger=on_trigger,
    )

    await scheduler.check_once()
    assert len(triggered) == 1
