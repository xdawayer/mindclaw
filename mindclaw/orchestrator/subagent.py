# input: orchestrator/acp.py, config/schema.py
# output: 导出 SubAgentManager
# pos: 子 Agent 管理器，管理并发任务队列和结果汇总
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import uuid

from loguru import logger

from mindclaw.config.schema import MindClawConfig
from mindclaw.orchestrator.acp import AgentHandle, AgentStatus, TaskRequest, TaskResult

_DEFAULT_MAX_CONCURRENT = 3
_DEFAULT_TASK_TIMEOUT = 300.0


class SubAgentManager:
    """Manages sub-agent lifecycle: spawning, concurrency, results."""

    def __init__(
        self,
        config: MindClawConfig,
        max_concurrent: int = _DEFAULT_MAX_CONCURRENT,
        task_timeout: float = _DEFAULT_TASK_TIMEOUT,
    ) -> None:
        self._config = config
        self._max_concurrent = max_concurrent
        self._task_timeout = task_timeout
        self._handles: dict[str, AgentHandle] = {}

    @property
    def active_count(self) -> int:
        return sum(
            1 for h in self._handles.values()
            if h.status == AgentStatus.RUNNING
        )

    def _clean_completed(self) -> None:
        """Remove handles for tasks that have completed or failed."""
        completed = [
            tid for tid, h in self._handles.items()
            if h.status != AgentStatus.RUNNING
        ]
        for tid in completed:
            del self._handles[tid]

    async def spawn(self, task: str, tools: list[str]) -> str:
        """Spawn a new sub-agent task. Returns task_id.

        Raises RuntimeError if max concurrent limit reached.
        """
        self._clean_completed()

        if self.active_count >= self._max_concurrent:
            raise RuntimeError(
                f"Cannot spawn: max concurrent limit ({self._max_concurrent}) reached"
            )

        task_id = uuid.uuid4().hex[:12]
        request = TaskRequest(
            task_id=task_id,
            task=task,
            model=self._config.agent.default_model,
            tools=tools,
            max_iterations=self._config.agent.subagent_max_iterations,
        )

        handle = await AgentHandle.spawn(
            task=request,
            timeout=self._task_timeout,
        )
        self._handles[task_id] = handle
        logger.info(f"SubAgent spawned: task_id={task_id}, task={task[:50]}")
        return task_id

    async def wait(self, task_id: str) -> TaskResult | None:
        """Wait for a task to complete and return its result."""
        handle = self._handles.get(task_id)
        if handle is None:
            return None
        return await handle.wait()

    async def kill(self, task_id: str) -> None:
        """Kill a specific sub-agent task."""
        handle = self._handles.get(task_id)
        if handle is not None:
            await handle.kill()

    async def kill_all(self) -> None:
        """Kill all active sub-agent tasks."""
        for handle in self._handles.values():
            if handle.status == AgentStatus.RUNNING:
                await handle.kill()
