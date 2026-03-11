# input: mindclaw.tools.dashboard_export
# output: DashboardExportTool 测试
# pos: 系统仪表盘导出工具 (HTML生成/任务状态/成功率计算/文件写入/路径沙箱) 测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock

import pytest

from mindclaw.orchestrator.cron_logger import CronRunLogger
from mindclaw.orchestrator.cron_store import CronTaskStore
from mindclaw.tools.base import RiskLevel


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def mock_store_with_tasks():
    store = AsyncMock(spec=CronTaskStore)
    store.load = AsyncMock(return_value={
        "task-1": {
            "name": "backup",
            "cron_expr": "0 3 * * *",
            "enabled": True,
            "last_run": "2026-03-11T03:00:00",
        },
        "task-2": {
            "name": "morning-brief",
            "cron_expr": "0 8 * * *",
            "enabled": False,
            "last_run": "2026-03-10T08:00:00",
        },
    })
    return store


@pytest.fixture
def mock_store_empty():
    store = AsyncMock(spec=CronTaskStore)
    store.load = AsyncMock(return_value={})
    return store


@pytest.fixture
def run_logger_with_runs(data_dir):
    logger = CronRunLogger(data_dir=data_dir)
    logger.log_run("backup", "success", "2026-03-11T03:00:00", "2026-03-11T03:01:00")
    logger.log_run("backup", "success", "2026-03-10T03:00:00", "2026-03-10T03:01:00")
    logger.log_run(
        "morning-brief", "success", "2026-03-11T08:00:00", "2026-03-11T08:00:30",
    )
    logger.log_run(
        "backup", "failed", "2026-03-09T03:00:00", "2026-03-09T03:00:05",
        error="timeout",
    )
    return logger


@pytest.fixture
def run_logger_empty(data_dir):
    return CronRunLogger(data_dir=data_dir)


@pytest.mark.asyncio
async def test_generates_html_file(mock_store_with_tasks, run_logger_with_runs, data_dir):
    """execute() should create an HTML file at the given output_path."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_with_tasks,
        run_logger=run_logger_with_runs,
    )
    await tool.execute({"output_path": "dashboard.html"})

    output_path = data_dir / "dashboard.html"
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert content.strip().startswith("<!DOCTYPE html>") or "<html" in content


@pytest.mark.asyncio
async def test_html_contains_tasks(mock_store_with_tasks, run_logger_with_runs, data_dir):
    """Generated HTML should include task names and cron expressions."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_with_tasks,
        run_logger=run_logger_with_runs,
    )
    await tool.execute({"output_path": "dashboard.html"})

    content = (data_dir / "dashboard.html").read_text(encoding="utf-8")
    assert "backup" in content
    assert "morning-brief" in content
    assert "0 3 * * *" in content
    assert "0 8 * * *" in content


@pytest.mark.asyncio
async def test_html_contains_runs(mock_store_with_tasks, run_logger_with_runs, data_dir):
    """Generated HTML should include recent execution records."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_with_tasks,
        run_logger=run_logger_with_runs,
    )
    await tool.execute({"output_path": "dashboard.html"})

    content = (data_dir / "dashboard.html").read_text(encoding="utf-8")
    assert "backup" in content
    assert "success" in content
    assert "failed" in content


@pytest.mark.asyncio
async def test_success_rate_calculation(mock_store_with_tasks, data_dir):
    """3 success + 1 failed runs should give 75% success rate."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    run_logger = CronRunLogger(data_dir=data_dir)
    run_logger.log_run("t", "success", "2026-03-11T01:00:00", "2026-03-11T01:00:10")
    run_logger.log_run("t", "success", "2026-03-11T02:00:00", "2026-03-11T02:00:10")
    run_logger.log_run("t", "success", "2026-03-11T03:00:00", "2026-03-11T03:00:10")
    run_logger.log_run(
        "t", "failed", "2026-03-11T04:00:00", "2026-03-11T04:00:10", error="err",
    )

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_with_tasks,
        run_logger=run_logger,
    )
    result = await tool.execute({"output_path": "rate.html"})

    assert "75" in result


@pytest.mark.asyncio
async def test_empty_tasks_and_runs(mock_store_empty, run_logger_empty, data_dir):
    """Tool should generate valid HTML even when there are no tasks or runs."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    result = await tool.execute({"output_path": "empty.html"})

    output_path = data_dir / "empty.html"
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "<html" in content
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_default_output_path(data_dir, mock_store_empty, run_logger_empty):
    """When no output_path, writes to data_dir/data/dashboard.html."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    await tool.execute({})

    default_path = data_dir / "data" / "dashboard.html"
    assert default_path.exists()


@pytest.mark.asyncio
async def test_custom_output_path(mock_store_empty, run_logger_empty, data_dir):
    """Tool should write to the specified custom output_path within data_dir."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    result = await tool.execute({"output_path": "reports/my_dashboard.html"})

    custom = data_dir / "reports" / "my_dashboard.html"
    assert custom.exists()
    assert "my_dashboard.html" in result


@pytest.mark.asyncio
async def test_creates_parent_dirs(mock_store_empty, run_logger_empty, data_dir):
    """Tool should create parent directories if they do not exist."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    nested = data_dir / "a" / "b" / "c"
    assert not nested.exists()

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    await tool.execute({"output_path": "a/b/c/dashboard.html"})

    assert (data_dir / "a" / "b" / "c" / "dashboard.html").exists()


@pytest.mark.asyncio
async def test_path_traversal_blocked(mock_store_empty, run_logger_empty, data_dir):
    """Path traversal via ../.. should be rejected."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    result = await tool.execute({"output_path": "../../etc/evil.html"})

    assert "Error" in result
    assert "data directory" in result


@pytest.mark.asyncio
async def test_return_message(mock_store_with_tasks, run_logger_with_runs, data_dir):
    """Return message follows expected format with counts."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_with_tasks,
        run_logger=run_logger_with_runs,
    )
    result = await tool.execute({"output_path": "dashboard.html"})

    assert "Dashboard generated:" in result
    assert "tasks" in result
    assert "recent runs" in result
    assert "%" in result
    assert "success" in result


@pytest.mark.asyncio
async def test_risk_level_moderate(data_dir, mock_store_empty, run_logger_empty):
    """DashboardExportTool should have MODERATE risk level."""
    from mindclaw.tools.dashboard_export import DashboardExportTool

    tool = DashboardExportTool(
        data_dir=data_dir,
        cron_store=mock_store_empty,
        run_logger=run_logger_empty,
    )
    assert tool.risk_level == RiskLevel.MODERATE
