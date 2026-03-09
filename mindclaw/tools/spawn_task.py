# input: tools/base.py, orchestrator/subagent.py
# output: 导出 SpawnTaskTool
# pos: 派发子 Agent 任务的工具，dangerous 级别需用户审批
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

from loguru import logger

from mindclaw.orchestrator.subagent import SubAgentManager

from .base import RiskLevel, Tool


class SpawnTaskTool(Tool):
    """Spawn a sub-agent to handle a subtask in a separate process."""

    name = "spawn_task"
    description = (
        "Spawn a sub-agent to handle a subtask in parallel. "
        "The sub-agent runs in a separate process and returns its result. "
        "Use this for tasks that can be broken down into independent pieces."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Description of the subtask for the sub-agent to complete",
            },
        },
        "required": ["task"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, manager: SubAgentManager) -> None:
        self._manager = manager

    async def execute(self, params: dict) -> str:
        task_desc = params["task"]
        logger.info(f"Spawning sub-agent for: {task_desc[:80]}")

        try:
            task_id = await self._manager.spawn(task=task_desc, tools=[])
        except RuntimeError as e:
            return f"Error: {e}"

        result = await self._manager.wait(task_id)
        if result is None:
            return "Error: sub-agent returned no result"

        if result.status == "completed":
            return result.content
        return f"Sub-agent failed: {result.error or 'unknown error'}"
