# input: asyncio, json
# output: 导出 AgentHandle, AgentStatus, TaskRequest, TaskResult
# pos: ACP 协议核心，管理子 Agent 进程生命周期和 JSON stdin/stdout 通信
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from enum import Enum

from loguru import logger

_FORBIDDEN_SUBAGENT_TOOLS = frozenset({"spawn_task", "message_user"})


class AgentStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    task: str
    model: str
    tools: list[str]
    max_iterations: int = 15

    def __post_init__(self) -> None:
        forbidden = _FORBIDDEN_SUBAGENT_TOOLS & set(self.tools)
        if forbidden:
            raise ValueError(
                f"Sub-agent tools cannot include: {', '.join(sorted(forbidden))}"
            )

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "task": self.task,
            "model": self.model,
            "tools": self.tools,
            "max_iterations": self.max_iterations,
        })


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str
    content: str
    error: str | None = None

    @classmethod
    def from_json(cls, raw: str) -> TaskResult:
        data = json.loads(raw)
        for field in ("task_id", "status"):
            if field not in data:
                raise ValueError(f"TaskResult JSON missing required field '{field}'")
        return cls(
            task_id=data["task_id"],
            status=data["status"],
            content=data.get("content", ""),
            error=data.get("error"),
        )


class AgentHandle:
    """Manages a single sub-agent child process via JSON stdin/stdout."""

    def __init__(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        timeout: float,
    ) -> None:
        self._task_id = task_id
        self._process = process
        self._timeout = timeout
        self._status = AgentStatus.RUNNING
        self._result: TaskResult | None = None

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def result(self) -> TaskResult | None:
        return self._result

    @classmethod
    async def spawn(
        cls,
        task: TaskRequest,
        python_path: str = "python3",
        runner_module: str = "mindclaw.orchestrator.subagent_runner",
        timeout: float = 300.0,
    ) -> AgentHandle:
        process = await asyncio.create_subprocess_exec(
            python_path, "-m", runner_module,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"Spawned subagent pid={process.pid} task_id={task.task_id}")

        handle = cls(task_id=task.task_id, process=process, timeout=timeout)

        # Send task request via stdin
        if process.stdin is None:
            raise RuntimeError("Subprocess stdin is not available")
        request_line = task.to_json() + "\n"
        process.stdin.write(request_line.encode())
        await process.stdin.drain()
        process.stdin.close()

        return handle

    async def stop(self) -> None:
        """Gracefully stop the subprocess (SIGTERM, then wait)."""
        if self._process.returncode is not None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
            self._status = AgentStatus.FAILED
            if self._result is None:
                self._result = TaskResult(
                    task_id=self._task_id,
                    status="failed",
                    content="",
                    error="Subagent was stopped",
                )
        except (asyncio.TimeoutError, ProcessLookupError, OSError):
            await self.kill()

    async def wait(self) -> TaskResult:
        """Wait for the subprocess to finish and return its result."""
        if self._result is not None:
            return self._result

        try:
            stdout_data, _ = await asyncio.wait_for(
                self._process.communicate(),
                timeout=self._timeout,
            )
            output = stdout_data.decode("utf-8", errors="replace").strip()

            if output:
                self._result = TaskResult.from_json(output)
                self._status = (
                    AgentStatus.COMPLETED
                    if self._result.status == "completed"
                    else AgentStatus.FAILED
                )
            else:
                self._result = TaskResult(
                    task_id=self._task_id,
                    status="failed",
                    content="",
                    error="No output from subagent",
                )
                self._status = AgentStatus.FAILED

        except asyncio.TimeoutError:
            logger.warning(f"Subagent timeout: task_id={self._task_id}")
            await self.kill()
            self._status = AgentStatus.TIMEOUT
            self._result = TaskResult(
                task_id=self._task_id,
                status="timeout",
                content="",
                error=f"Subagent timed out after {self._timeout}s",
            )

        except Exception as e:
            logger.error(f"Subagent error: task_id={self._task_id}: {e}")
            self._status = AgentStatus.FAILED
            self._result = TaskResult(
                task_id=self._task_id,
                status="failed",
                content="",
                error=str(e),
            )

        return self._result

    async def kill(self) -> None:
        """Forcefully terminate the subprocess."""
        if self._process.returncode is not None:
            return
        try:
            self._process.kill()
            await self._process.wait()
        except (ProcessLookupError, OSError):
            pass
        self._status = AgentStatus.FAILED
        if self._result is None:
            self._result = TaskResult(
                task_id=self._task_id,
                status="failed",
                content="",
                error="Subagent was killed",
            )
        logger.info(f"Killed subagent: task_id={self._task_id}")
