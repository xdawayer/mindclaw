# input: mindclaw.tools.cron, mindclaw.orchestrator.cron_logger
# output: CronHistoryTool 测试
# pos: 验证 cron 执行历史查询工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.orchestrator.cron_logger import CronRunLogger


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def run_logger(data_dir):
    return CronRunLogger(data_dir=data_dir)


# ── CronHistoryTool basics ────────────────────────────────────


@pytest.mark.asyncio
async def test_history_tool_returns_recent_runs(data_dir, run_logger):
    """CronHistoryTool should return recent execution records."""
    from mindclaw.tools.cron import CronHistoryTool

    run_logger.log_run(
        task_name="backup",
        status="success",
        started_at="2026-03-10T10:00:00",
        finished_at="2026-03-10T10:01:00",
    )
    run_logger.log_run(
        task_name="backup",
        status="failed",
        started_at="2026-03-10T11:00:00",
        finished_at="2026-03-10T11:00:05",
        error="timeout",
    )

    tool = CronHistoryTool(run_logger=run_logger)
    result = await tool.execute({})

    assert "backup" in result
    assert "success" in result
    assert "failed" in result


@pytest.mark.asyncio
async def test_history_tool_filters_by_task_name(data_dir, run_logger):
    """CronHistoryTool with task_name param should filter results."""
    from mindclaw.tools.cron import CronHistoryTool

    run_logger.log_run(
        task_name="alpha",
        status="success",
        started_at="2026-03-10T10:00:00",
        finished_at="2026-03-10T10:01:00",
    )
    run_logger.log_run(
        task_name="beta",
        status="success",
        started_at="2026-03-10T11:00:00",
        finished_at="2026-03-10T11:01:00",
    )

    tool = CronHistoryTool(run_logger=run_logger)
    result = await tool.execute({"task_name": "alpha"})

    assert "alpha" in result
    assert "beta" not in result


@pytest.mark.asyncio
async def test_history_tool_empty_history(data_dir, run_logger):
    """CronHistoryTool should return 'No execution history' when empty."""
    from mindclaw.tools.cron import CronHistoryTool

    tool = CronHistoryTool(run_logger=run_logger)
    result = await tool.execute({})

    assert "no" in result.lower() or "empty" in result.lower()


@pytest.mark.asyncio
async def test_history_tool_respects_limit(data_dir, run_logger):
    """CronHistoryTool should respect the limit parameter."""
    from mindclaw.tools.cron import CronHistoryTool

    for i in range(10):
        run_logger.log_run(
            task_name="task",
            status="success",
            started_at=f"2026-03-10T{i:02d}:00:00",
            finished_at=f"2026-03-10T{i:02d}:00:01",
        )

    tool = CronHistoryTool(run_logger=run_logger)
    result = await tool.execute({"limit": 3})

    # Should show only 3 entries' started_at timestamps
    assert result.count("success") == 3


@pytest.mark.asyncio
async def test_history_tool_risk_level(data_dir, run_logger):
    """CronHistoryTool should have SAFE risk level."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.cron import CronHistoryTool

    tool = CronHistoryTool(run_logger=run_logger)
    assert tool.risk_level == RiskLevel.SAFE
