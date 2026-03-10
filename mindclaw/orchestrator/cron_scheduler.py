# input: croniter, json, asyncio, pathlib
# output: 导出 CronScheduler
# pos: 后台 cron 调度器，按 croniter 表达式定时触发任务
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Background cron scheduler: checks cron_tasks.json and triggers due tasks."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from croniter import CroniterBadCronError, croniter
from loguru import logger

_TASKS_FILE = "cron_tasks.json"

# Callback type: async def on_trigger(name: str, action: str) -> None
OnTriggerCallback = Callable[[str, str], Awaitable[None] | None]


class CronScheduler:
    """Background scheduler that checks cron_tasks.json and triggers due tasks."""

    def __init__(
        self,
        data_dir: Path,
        on_trigger: OnTriggerCallback,
        check_interval: float = 60.0,
    ) -> None:
        self._data_dir = data_dir
        self._on_trigger = on_trigger
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._file_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def task_count(self) -> int:
        return len(self._load_tasks())

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
        async with self._file_lock:
            tasks = self._load_tasks()
            now = datetime.now()

            for task_id, task in tasks.items():
                if self._is_due(task, now):
                    await self._trigger(task_id, task, now)

    def _load_tasks(self) -> dict[str, Any]:
        tasks_file = self._data_dir / _TASKS_FILE
        if not tasks_file.exists():
            return {}
        try:
            return json.loads(tasks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read cron_tasks.json")
            return {}

    def _save_tasks(self, tasks: dict) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        tasks_file = self._data_dir / _TASKS_FILE
        tasks_file.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")

    def _is_due(self, task: dict, now: datetime) -> bool:
        """Check if a task is due to run based on its cron expression and last_run."""
        try:
            cron_expr = task["cron_expr"]
            last_run_str = task.get("last_run")

            if last_run_str:
                last_run = datetime.fromisoformat(last_run_str)
            else:
                # Never run before — use created_at as baseline so task
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
        name = task["name"]
        action = task["action"]

        logger.info(f"Cron trigger: {name} ({task_id})")

        try:
            result = self._on_trigger(name, action)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                await result
        except Exception:
            logger.exception(f"Cron task '{name}' failed")
            return  # Don't update last_run on failure — task will retry next cycle

        # Update last_run only on success
        tasks = self._load_tasks()
        if task_id in tasks:
            tasks[task_id]["last_run"] = now.isoformat()
            self._save_tasks(tasks)

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.check_once()
            except Exception:
                logger.exception("CronScheduler check cycle error")
            await asyncio.sleep(self._check_interval)
