# input: tools/base.py, asyncio
# output: TwitterReadTool
# pos: X/Twitter 读取工具，通过 CLI 子进程安全执行
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from loguru import logger

from .base import RiskLevel, Tool

_SHELL_META = frozenset(';|&$`(){}><\n\r')

_MAX_COUNT = 50
_DEFAULT_COUNT = 10
_TIMEOUT = 30


class TwitterReadTool(Tool):
    name = "twitter_read"
    description = "Read X/Twitter timeline, search posts, or get user posts via CLI tool"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["timeline", "search", "user"],
                "description": "Action to perform: timeline, search, or user",
            },
            "query": {
                "type": "string",
                "description": "Search term or username (required for search and user actions)",
            },
            "count": {
                "type": "integer",
                "description": "Number of posts to retrieve (default 10, max 50)",
            },
        },
        "required": ["action"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 5000

    def __init__(self, cli_path: str) -> None:
        self.cli_path = cli_path

    async def execute(self, params: dict) -> str:
        action = params.get("action", "")
        query = params.get("query", "")
        try:
            count = min(int(params.get("count", _DEFAULT_COUNT)), _MAX_COUNT)
        except (TypeError, ValueError):
            return "Error: 'count' must be an integer"

        if action in ("search", "user") and not query:
            return f"Error: 'query' parameter is required for action '{action}'"

        if query and _contains_shell_meta(query):
            logger.warning(f"Rejected query with shell metacharacters: {query!r}")
            return "Error: invalid characters in query (shell metacharacters are not allowed)"

        if not self.cli_path:
            return "Error: twitter CLI path is not configured (cli_path is empty)"

        cmd = [self.cli_path, action, "--count", str(count)]
        if action in ("search", "user") and query:
            cmd += ["--query", query]

        logger.info(f"Executing twitter CLI: {cmd}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            logger.warning(f"twitter CLI timed out after {_TIMEOUT}s")
            return f"Error: twitter CLI timed out after {_TIMEOUT}s"
        except FileNotFoundError as exc:
            logger.error(f"twitter CLI binary not found: {exc}")
            return f"Error: twitter CLI binary not found at '{self.cli_path}'"
        except Exception as exc:
            logger.error(f"twitter CLI error: {exc}")
            return f"Error executing twitter CLI: {exc}"

        output = stdout.decode("utf-8", errors="replace").strip()
        if stderr:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            if err_text:
                logger.warning(f"twitter CLI stderr: {err_text}")
                if not output:
                    output = "Error: twitter CLI reported an error (see logs)"

        if self.max_result_chars and len(output) > self.max_result_chars:
            output = output[: self.max_result_chars] + "\n[truncated]"

        return output


def _contains_shell_meta(text: str) -> bool:
    return any(ch in _SHELL_META for ch in text)
