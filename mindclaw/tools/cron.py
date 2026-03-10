# input: tools/base.py, croniter, orchestrator/cron_store.py
# output: 导出 CronAddTool, CronListTool, CronRemoveTool, CronToggleTool
# pos: 定时任务工具，通过 CronTaskStore 管理 cron 任务的 CRUD
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Cron task management tools: add, list, remove, toggle scheduled tasks."""

from __future__ import annotations

import uuid
from datetime import datetime

from croniter import CroniterBadCronError, croniter
from loguru import logger

from mindclaw.orchestrator.cron_store import CronTaskStore
from mindclaw.tools.base import RiskLevel, Tool


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
            "notify_channel": {
                "type": "string",
                "description": "Channel to send results to (e.g. telegram, slack, feishu)",
            },
            "notify_chat_id": {
                "type": "string",
                "description": "Chat ID to send results to",
            },
            "max_iterations": {
                "type": "integer",
                "description": "Max agent iterations for this task (default 15)",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 300)",
            },
        },
        "required": ["name", "cron_expr", "action"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, store: CronTaskStore) -> None:
        self._store = store

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

        task_id = f"cron_{uuid.uuid4().hex[:8]}"
        task_dict: dict = {
            "name": name,
            "cron_expr": cron_expr,
            "action": action,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "enabled": True,
        }

        # Optional fields
        for key in ("notify_channel", "notify_chat_id"):
            if params.get(key):
                task_dict[key] = params[key]
        if "max_iterations" in params:
            task_dict["max_iterations"] = params["max_iterations"]
        if "timeout" in params:
            task_dict["timeout"] = params["timeout"]

        # Atomic check-and-add to prevent TOCTOU race on duplicate names
        added = await self._store.add_if_name_unique(task_id, task_dict)
        if not added:
            return f"Error: Task with name '{name}' already exists"
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

    def __init__(self, store: CronTaskStore) -> None:
        self._store = store

    async def execute(self, params: dict) -> str:
        tasks = await self._store.load()

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
            enabled = task.get("enabled", True)
            status = "on" if enabled else "OFF"
            notify = task.get("notify_channel", "")
            notify_suffix = f" -> {notify}" if notify else ""

            lines.append(
                f"- [{task_id}] {task['name']} [{status}]: {task['cron_expr']} "
                f"| action: {task['action']} "
                f"| next: {next_run} | last: {last_run}{notify_suffix}"
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

    def __init__(self, store: CronTaskStore) -> None:
        self._store = store

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        removed = await self._store.remove(task_id)

        if removed is None:
            return f"Error: Task '{task_id}' not found"

        logger.info(f"Cron task removed: {removed['name']} ({task_id})")
        return f"Task '{removed['name']}' (ID: {task_id}) removed."


class CronToggleTool(Tool):
    name = "cron_toggle"
    description = "Enable or disable a scheduled cron task"
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "The task ID to toggle"},
            "enabled": {"type": "boolean", "description": "True to enable, False to disable"},
        },
        "required": ["task_id", "enabled"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, store: CronTaskStore) -> None:
        self._store = store

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        enabled = params["enabled"]

        task = await self._store.get(task_id)
        if task is None:
            return f"Error: Task '{task_id}' not found"

        await self._store.set_enabled(task_id, enabled)
        state = "enabled" if enabled else "disabled"
        logger.info(f"Cron task {state}: {task['name']} ({task_id})")
        return f"Task '{task['name']}' (ID: {task_id}) {state}."
