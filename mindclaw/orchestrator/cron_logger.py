# input: json, pathlib
# output: 导出 CronRunLogger
# pos: Cron 执行日志记录器，追加写入 JSONL 格式执行记录
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Cron run execution logger -- appends JSON lines to cron_runs.jsonl."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from loguru import logger

_LOG_FILE = "cron_runs.jsonl"
_MAX_TASK_NAME_LEN = 256
_MAX_READ_LINES = 10_000


class CronRunLogger:
    """Appends cron task execution records to a JSONL file.

    Each record is a single JSON line containing task_name, status,
    started_at, finished_at, and error fields.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._log_path = data_dir / _LOG_FILE

    def log_run(
        self,
        task_name: str,
        status: str,
        started_at: str,
        finished_at: str,
        error: str = "",
    ) -> None:
        """Append a single execution record as a JSON line."""
        task_name = task_name[:_MAX_TASK_NAME_LEN]
        entry = {
            "task_name": task_name,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "error": error,
        }
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            logger.warning("Failed to write cron run log entry for task '{}'", task_name)

    def recent_runs(
        self,
        task_name: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Read and return recent run entries from the log file.

        Args:
            task_name: When provided, only entries matching this name are returned.
            limit: Maximum number of entries to return (most recent first from tail).

        Returns:
            A list of run entry dicts, ordered from oldest to most recent.
        """
        if not self._log_path.exists():
            return []

        try:
            with self._log_path.open("r", encoding="utf-8") as fh:
                tail = deque(fh, maxlen=_MAX_READ_LINES)
        except OSError:
            logger.warning("Failed to read cron run log")
            return []

        entries: list[dict] = []
        for raw_line in tail:
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed cron log line: {!r}", line)
                continue
            if task_name is None or entry.get("task_name") == task_name:
                entries.append(entry)

        return entries[-limit:]
