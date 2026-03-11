# input: croniter, asyncio, orchestrator/cron_store.py
# output: 导出 CronScheduler
# pos: 后台 cron 调度器，按 croniter 表达式定时触发任务
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Background cron scheduler: reads tasks via CronTaskStore and triggers due tasks."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime
from typing import Awaitable, Callable

from croniter import CroniterBadCronError, croniter
from loguru import logger

from mindclaw.orchestrator.cron_store import CronTaskStore

# Callback receives (task_id, full_task_dict) so caller can read notify_channel etc.
OnTriggerCallback = Callable[[str, dict], Awaitable[None] | None]


class CronScheduler:
    """Background scheduler that reads tasks via CronTaskStore and triggers due tasks."""

    def __init__(
        self,
        store: CronTaskStore,
        on_trigger: OnTriggerCallback,
        check_interval: float = 60.0,
        global_enabled_fn: Callable[[], bool] | None = None,
    ) -> None:
        self._store = store
        self._on_trigger = on_trigger
        self._check_interval = check_interval
        self._global_enabled_fn = global_enabled_fn
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("CronScheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("CronScheduler stopped")

    async def check_once(self) -> None:
        """Run a single check cycle (for testing)."""
        if self._global_enabled_fn is not None and not self._global_enabled_fn():
            return

        tasks = await self._store.load()
        now = datetime.now()

        for task_id, task in tasks.items():
            if not task.get("enabled", True):
                continue
            if self._is_due(task, now):
                await self._trigger(task_id, task, now)

    @staticmethod
    def _is_due(task: dict, now: datetime) -> bool:
        """Check if a task is due to run based on its cron expression and last_run."""
        try:
            cron_expr = task["cron_expr"]
            last_run_str = task.get("last_run")

            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str)
            else:
                # Never run before -- use created_at as baseline so task
                # waits until its first scheduled time after creation.
                created_str = task.get("created_at")
                if created_str:
                    last_run = datetime.fromisoformat(created_str)
                else:
                    last_run = now

            cron = croniter(cron_expr, last_run)
            next_run = cron.get_next(datetime)
            return next_run <= now
        except (CroniterBadCronError, ValueError, KeyError):
            return False

    async def _trigger(self, task_id: str, task: dict, now: datetime) -> None:
        name = task.get("name", task_id)

        logger.info(f"Cron trigger: {name} ({task_id})")

        try:
            result = self._on_trigger(task_id, task)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(f"Cron task '{name}' failed")
            return  # Don't update last_run on failure -- task will retry next cycle

        # Update last_run only on success
        await self._store.update_last_run(task_id, now.isoformat())

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.check_once()
            except Exception:
                logger.exception("CronScheduler check cycle error")
            await asyncio.sleep(self._check_interval)
