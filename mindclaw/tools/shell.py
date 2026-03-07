# input: tools/base.py, security/sandbox.py, asyncio
# output: 导出 ExecTool
# pos: Shell 执行工具，含超时保护，命令黑名单委托给 security/sandbox
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import os
import signal
from pathlib import Path

from loguru import logger

from mindclaw.security.sandbox import is_command_denied

from .base import RiskLevel, Tool


class ExecTool(Tool):
    name = "exec"
    description = "Execute a shell command and return its output. Use with caution."
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
        "required": ["command"],
    }
    risk_level = RiskLevel.DANGEROUS

    def __init__(self, workspace: Path, timeout: int = 30) -> None:
        self.workspace = workspace
        self.timeout = timeout

    async def execute(self, params: dict) -> str:
        command = params["command"]

        if is_command_denied(command):
            logger.warning(f"Blocked denied command: {command}")
            return "Error: command denied by security policy"

        logger.info(f"Executing: {command}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                start_new_session=True,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = ""
            if output:
                result += output
            if errors:
                result += f"\nSTDERR:\n{errors}" if result else errors
            if not result:
                result = f"(exit code: {proc.returncode})"

            return result.strip()

        except asyncio.TimeoutError:
            logger.warning(f"Command timeout after {self.timeout}s: {command}")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            return f"Error: command timeout after {self.timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
