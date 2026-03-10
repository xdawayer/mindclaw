# input: asyncio, json, pathlib
# output: 导出 CronTaskStore
# pos: cron 任务持久化层，统一管理 cron_tasks.json 的读写，解决竞态问题
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Centralized cron task persistence with async locking and atomic writes."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

from loguru import logger

_TASKS_FILE = "cron_tasks.json"


class CronTaskStore:
    """Thread-safe, async-safe cron task storage with atomic file writes.

    Both CronScheduler and CronXxxTool classes should share a single instance
    to avoid race conditions on cron_tasks.json.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._lock = asyncio.Lock()

    @property
    def _tasks_path(self) -> Path:
        return self._data_dir / _TASKS_FILE

    # ── Read ──────────────────────────────────────────────────

    async def load(self) -> dict[str, dict]:
        """Load all tasks. Returns a deep copy (safe to mutate)."""
        async with self._lock:
            return self._read()

    async def get(self, task_id: str) -> dict | None:
        """Get a single task by ID, or None."""
        async with self._lock:
            tasks = self._read()
            task = tasks.get(task_id)
            return copy.deepcopy(task) if task is not None else None

    # ── Write ─────────────────────────────────────────────────

    async def add(self, task_id: str, task: dict) -> None:
        """Add a task. Overwrites if task_id already exists."""
        async with self._lock:
            tasks = self._read()
            tasks[task_id] = copy.deepcopy(task)
            self._write(tasks)

    async def add_if_name_unique(self, task_id: str, task: dict) -> bool:
        """Add a task only if no other task has the same name. Returns True on success."""
        async with self._lock:
            tasks = self._read()
            name = task.get("name", "")
            if any(t.get("name") == name for t in tasks.values()):
                return False
            tasks[task_id] = copy.deepcopy(task)
            self._write(tasks)
            return True

    async def remove(self, task_id: str) -> dict | None:
        """Remove a task by ID. Returns the removed task, or None."""
        async with self._lock:
            tasks = self._read()
            removed = tasks.pop(task_id, None)
            if removed is not None:
                self._write(tasks)
            return removed

    async def update_last_run(self, task_id: str, timestamp: str) -> None:
        """Update last_run for a task. Silently skips if task_id not found."""
        async with self._lock:
            tasks = self._read()
            if task_id not in tasks:
                return
            tasks[task_id]["last_run"] = timestamp
            self._write(tasks)

    async def set_enabled(self, task_id: str, enabled: bool) -> None:
        """Toggle enabled state. Silently skips if task_id not found."""
        async with self._lock:
            tasks = self._read()
            if task_id not in tasks:
                return
            tasks[task_id]["enabled"] = enabled
            self._write(tasks)

    # ── Internal I/O ──────────────────────────────────────────

    def _read(self) -> dict[str, dict]:
        """Read tasks from disk. Returns deep copy. Caller must hold _lock."""
        if not self._tasks_path.exists():
            return {}
        try:
            data = json.loads(self._tasks_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning("cron_tasks.json has unexpected format (not a dict), resetting")
                return {}
            return copy.deepcopy(data)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read cron_tasks.json")
            return {}

    def _write(self, tasks: dict) -> None:
        """Atomic write: write to .tmp then rename. Caller must hold _lock."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._tasks_path.with_suffix(".tmp")
        content = json.dumps(tasks, indent=2, ensure_ascii=False)
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(self._tasks_path)
        self._tasks_path.chmod(0o600)
