# input: sys, json
# output: 子进程入口 (通过 python -m 调用)
# pos: 子 Agent 子进程入口点，从 stdin 读取 TaskRequest，输出 TaskResult 到 stdout
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""SubAgent child process entry point.

Usage: python -m mindclaw.orchestrator.subagent_runner

Reads a single JSON TaskRequest from stdin, processes it, writes a JSON
TaskResult to stdout, then exits.

In Phase 6 this runner uses a simplified in-process loop (no actual LLM calls)
to validate the ACP protocol. Full LLM integration will be added when
SubAgentManager wires in the LLMRouter config.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    raw = sys.stdin.readline()
    if not raw.strip():
        _write_error("empty-0", "No input received on stdin")
        return

    try:
        request = json.loads(raw)
    except json.JSONDecodeError as e:
        _write_error("parse-err", f"Invalid JSON: {e}")
        return

    task_id = request.get("task_id", "unknown")
    task = request.get("task", "")

    result = {
        "task_id": task_id,
        "status": "completed",
        "content": f"SubAgent completed task: {task}",
    }
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


def _write_error(task_id: str, error: str) -> None:
    result = {
        "task_id": task_id,
        "status": "failed",
        "content": "",
        "error": error,
    }
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
