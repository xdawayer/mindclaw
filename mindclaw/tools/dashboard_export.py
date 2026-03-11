# input: tools/base.py, orchestrator/cron_store.py, orchestrator/cron_logger.py
# output: DashboardExportTool
# pos: 系统仪表盘导出工具，生成自包含 HTML 看板
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Dashboard export tool -- generates a self-contained HTML status dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from mindclaw.orchestrator.cron_logger import CronRunLogger
from mindclaw.orchestrator.cron_store import CronTaskStore
from mindclaw.tools.base import RiskLevel, Tool

_DEFAULT_OUTPUT_PATH = "data/dashboard.html"
_MAX_RECENT_RUNS = 20
_RUN_FETCH_LIMIT = 100


def _row_color(status: str) -> str:
    return "green" if status == "success" else "red"


def _task_rows(tasks: dict[str, dict]) -> str:
    if not tasks:
        return "<tr><td colspan='4'>No cron tasks configured.</td></tr>"
    rows = []
    for task in tasks.values():
        name = escape(str(task.get("name", "")))
        expr = escape(str(task.get("cron_expr", "")))
        last_run = escape(str(task.get("last_run", "—")))
        state = "enabled" if task.get("enabled", True) else "disabled"
        rows.append(
            f"<tr><td>{name}</td><td>{expr}</td><td>{last_run}</td><td>{state}</td></tr>"
        )
    return "\n".join(rows)


def _run_rows(runs: list[dict]) -> str:
    if not runs:
        return "<tr><td colspan='4'>No recent executions.</td></tr>"
    recent = runs[-_MAX_RECENT_RUNS:]
    rows = []
    for run in reversed(recent):
        task_name = escape(str(run.get("task_name", "")))
        status = escape(str(run.get("status", "")))
        started = escape(str(run.get("started_at", "")))
        finished = escape(str(run.get("finished_at", "")))
        color = _row_color(run.get("status", ""))
        rows.append(
            f'<tr><td>{task_name}</td>'
            f'<td style="color:{color}">{status}</td>'
            f'<td>{started}</td><td>{finished}</td></tr>'
        )
    return "\n".join(rows)


def _build_html(
    tasks: dict[str, dict],
    runs: list[dict],
    generated_at: str,
    success_rate: int,
) -> str:
    task_rows = _task_rows(tasks)
    run_rows = _run_rows(runs)
    n_tasks = len(tasks)
    n_runs = len(runs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MindClaw Dashboard</title>
<style>
  body {{ font-family: sans-serif; margin: 2rem; background: #f5f5f5; color: #333; }}
  h1 {{ color: #2c3e50; }}
  h2 {{ color: #34495e; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; margin-top: 0.5rem; }}
  th, td {{ padding: 0.5rem 1rem; border: 1px solid #ddd; text-align: left; }}
  th {{ background: #ecf0f1; }}
  .stat {{ font-size: 2rem; font-weight: bold; color: #2980b9; }}
</style>
</head>
<body>
<h1>MindClaw Dashboard</h1>

<h2>System Status</h2>
<p>Generated: {generated_at}</p>

<h2>Active Cron Tasks ({n_tasks})</h2>
<table>
  <tr><th>Name</th><th>Cron Expression</th><th>Last Run</th><th>State</th></tr>
  {task_rows}
</table>

<h2>Recent Executions (last {min(n_runs, _MAX_RECENT_RUNS)})</h2>
<table>
  <tr><th>Task</th><th>Status</th><th>Started</th><th>Finished</th></tr>
  {run_rows}
</table>

<h2>Success Rate</h2>
<p class="stat">{success_rate}%</p>
<p>Total executions: {n_runs}</p>
</body>
</html>"""


def _calculate_success_rate(runs: list[dict]) -> int:
    if not runs:
        return 0
    successes = sum(1 for r in runs if r.get("status") == "success")
    return round(successes / len(runs) * 100)


class DashboardExportTool(Tool):
    name = "dashboard_export"
    description = "Generate a self-contained HTML dashboard with system status and cron task health"
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": f"Output file path (default: {_DEFAULT_OUTPUT_PATH})",
            },
        },
        "required": [],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 500

    def __init__(
        self,
        data_dir: Path,
        cron_store: CronTaskStore,
        run_logger: CronRunLogger,
    ) -> None:
        self._data_dir = data_dir
        self._cron_store = cron_store
        self._run_logger = run_logger

    async def execute(self, params: dict) -> str:
        output_path_str: str = params.get("output_path", _DEFAULT_OUTPUT_PATH)
        output_path = (self._data_dir / output_path_str).resolve()
        allowed_root = self._data_dir.resolve()
        if not str(output_path).startswith(str(allowed_root) + "/") and output_path != allowed_root:
            return "Error: output_path must be inside the data directory"

        tasks = await self._cron_store.load()
        runs = self._run_logger.recent_runs(limit=_RUN_FETCH_LIMIT)

        success_rate = _calculate_success_rate(runs)
        generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        html = _build_html(tasks, runs, generated_at, success_rate)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        n_tasks = len(tasks)
        n_runs = len(runs)
        return (
            f"Dashboard generated: {output_path} "
            f"({n_tasks} tasks, {n_runs} recent runs, {success_rate}% success)"
        )
