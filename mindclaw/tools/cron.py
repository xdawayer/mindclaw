# input: tools/base.py, croniter, json, pathlib
# output: 导出 CronAddTool, CronListTool, CronRemoveTool
# pos: 定时任务工具，管理 cron 任务的 CRUD 和持久化
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Cron task management tools: add, list, remove scheduled tasks."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from croniter import CroniterBadCronError, croniter
from loguru import logger

from mindclaw.tools.base import RiskLevel, Tool

_TASKS_FILE = "cron_tasks.json"


def _load_tasks(data_dir: Path) -> dict:
    tasks_file = data_dir / _TASKS_FILE
    if not tasks_file.exists():
        return {}
    return json.loads(tasks_file.read_text(encoding="utf-8"))


def _save_tasks(data_dir: Path, tasks: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    tasks_file = data_dir / _TASKS_FILE
    tasks_file.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")


class CronAddTool(Tool):
    name = "cron_add"
    description = "Add a scheduled task with a cron expression"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Task name (unique identifier)"},
            "cron_expr": {
                "type": "string",
                "description": "Cron expression (e.g. '0 22 * * *' for 10 PM daily)",
            },
            "action": {
                "type": "string",
                "description": "What to do when triggered (natural language instruction)",
            },
        },
        "required": ["name", "cron_expr", "action"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def execute(self, params: dict) -> str:
        name = params["name"]
        cron_expr = params["cron_expr"]
        action = params["action"]

        # Validate cron expression
        try:
            cron = croniter(cron_expr)
            next_run = cron.get_next(datetime)
        except (CroniterBadCronError, ValueError, KeyError):
            return f"Error: Invalid cron expression '{cron_expr}'"

        tasks = _load_tasks(self._data_dir)

        # Check for duplicate name
        for task in tasks.values():
            if task["name"] == name:
                return f"Error: Task with name '{name}' already exists"

        task_id = f"cron_{uuid.uuid4().hex[:8]}"
        tasks[task_id] = {
            "name": name,
            "cron_expr": cron_expr,
            "action": action,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
        }

        _save_tasks(self._data_dir, tasks)
        logger.info(f"Cron task added: {name} ({cron_expr})")

        return (
            f"Task '{name}' added (ID: {task_id}). "
            f"Schedule: {cron_expr}. Next run: {next_run.strftime('%Y-%m-%d %H:%M')}"
        )


class CronListTool(Tool):
    name = "cron_list"
    description = "List all scheduled cron tasks"
    parameters = {"type": "object", "properties": {}}
    risk_level = RiskLevel.SAFE

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def execute(self, params: dict) -> str:
        tasks = _load_tasks(self._data_dir)

        if not tasks:
            return "No scheduled tasks."

        lines = []
        for task_id, task in tasks.items():
            try:
                cron = croniter(task["cron_expr"])
                next_run = cron.get_next(datetime).strftime("%Y-%m-%d %H:%M")
            except (CroniterBadCronError, ValueError, KeyError):
                next_run = "invalid"

            last_run = task.get("last_run") or "never"
            lines.append(
                f"- [{task_id}] {task['name']}: {task['cron_expr']} "
                f"| action: {task['action']} "
                f"| next: {next_run} | last: {last_run}"
            )

        return "\n".join(lines)


class CronRemoveTool(Tool):
    name = "cron_remove"
    description = "Remove a scheduled cron task by ID"
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "The task ID to remove"},
        },
        "required": ["task_id"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        tasks = _load_tasks(self._data_dir)

        if task_id not in tasks:
            return f"Error: Task '{task_id}' not found"

        removed = tasks.pop(task_id)
        _save_tasks(self._data_dir, tasks)
        logger.info(f"Cron task removed: {removed['name']} ({task_id})")

        return f"Task '{removed['name']}' (ID: {task_id}) removed."
