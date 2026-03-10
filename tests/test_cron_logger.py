# input: mindclaw.orchestrator.cron_logger
# output: CronRunLogger 测试
# pos: 验证 cron 执行日志的写入、读取和过滤
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

import pytest


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def logger_inst(data_dir):
    from mindclaw.orchestrator.cron_logger import CronRunLogger

    return CronRunLogger(data_dir=data_dir)


# ── File creation ─────────────────────────────────────────────


def test_log_run_creates_file(logger_inst, data_dir):
    """log_run() should create cron_runs.jsonl on first call."""
    assert not (data_dir / "cron_runs.jsonl").exists()
    logger_inst.log_run(
        task_name="backup",
        status="success",
        started_at="2026-03-10T10:00:00",
        finished_at="2026-03-10T10:01:00",
    )
    assert (data_dir / "cron_runs.jsonl").exists()


# ── Append behavior ───────────────────────────────────────────


def test_log_run_appends_entries(logger_inst, data_dir):
    """Each log_run() call should append a new JSON line."""
    logger_inst.log_run(
        task_name="backup",
        status="success",
        started_at="2026-03-10T10:00:00",
        finished_at="2026-03-10T10:01:00",
    )
    logger_inst.log_run(
        task_name="backup",
        status="failed",
        started_at="2026-03-10T11:00:00",
        finished_at="2026-03-10T11:00:05",
        error="timeout",
    )

    lines = (data_dir / "cron_runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["status"] == "success"
    assert second["status"] == "failed"


# ── recent_runs -- all entries ────────────────────────────────


def test_recent_runs_returns_all(logger_inst):
    """recent_runs() with no filters should return all entries (up to limit)."""
    for i in range(5):
        logger_inst.log_run(
            task_name=f"task-{i}",
            status="success",
            started_at=f"2026-03-10T0{i}:00:00",
            finished_at=f"2026-03-10T0{i}:00:01",
        )

    runs = logger_inst.recent_runs()
    assert len(runs) == 5


# ── recent_runs -- filter by task_name ───────────────────────


def test_recent_runs_filters_by_task_name(logger_inst):
    """recent_runs(task_name=...) should return only matching entries."""
    logger_inst.log_run(
        task_name="alpha",
        status="success",
        started_at="2026-03-10T09:00:00",
        finished_at="2026-03-10T09:00:01",
    )
    logger_inst.log_run(
        task_name="beta",
        status="success",
        started_at="2026-03-10T09:01:00",
        finished_at="2026-03-10T09:01:01",
    )
    logger_inst.log_run(
        task_name="alpha",
        status="failed",
        started_at="2026-03-10T10:00:00",
        finished_at="2026-03-10T10:00:02",
        error="err",
    )

    alpha_runs = logger_inst.recent_runs(task_name="alpha")
    assert len(alpha_runs) == 2
    assert all(r["task_name"] == "alpha" for r in alpha_runs)

    beta_runs = logger_inst.recent_runs(task_name="beta")
    assert len(beta_runs) == 1
    assert beta_runs[0]["task_name"] == "beta"


# ── recent_runs -- limit ──────────────────────────────────────


def test_recent_runs_limits_results(logger_inst):
    """recent_runs(limit=N) should return at most N entries (most recent)."""
    for i in range(10):
        logger_inst.log_run(
            task_name="task",
            status="success",
            started_at=f"2026-03-10T{i:02d}:00:00",
            finished_at=f"2026-03-10T{i:02d}:00:01",
        )

    runs = logger_inst.recent_runs(limit=3)
    assert len(runs) == 3
    # Most recent 3 entries (last written come last in file, so limit=3 from tail)
    assert runs[-1]["started_at"] == "2026-03-10T09:00:00"


# ── recent_runs -- empty file ─────────────────────────────────


def test_recent_runs_empty_file(logger_inst, data_dir):
    """recent_runs() on an empty file should return []."""
    (data_dir / "cron_runs.jsonl").write_text("", encoding="utf-8")
    runs = logger_inst.recent_runs()
    assert runs == []


# ── recent_runs -- nonexistent file ──────────────────────────


def test_recent_runs_nonexistent_file(logger_inst):
    """recent_runs() when file does not exist should return []."""
    runs = logger_inst.recent_runs()
    assert runs == []


# ── Entry format ──────────────────────────────────────────────


def test_log_run_entry_format(logger_inst, data_dir):
    """log_run() should write a valid JSON line with all required fields."""
    logger_inst.log_run(
        task_name="check-health",
        status="success",
        started_at="2026-03-10T08:00:00",
        finished_at="2026-03-10T08:00:03",
    )

    line = (data_dir / "cron_runs.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(line)

    assert "task_name" in entry
    assert "status" in entry
    assert "started_at" in entry
    assert "finished_at" in entry
    assert "error" in entry

    assert entry["task_name"] == "check-health"
    assert entry["status"] == "success"
    assert entry["started_at"] == "2026-03-10T08:00:00"
    assert entry["finished_at"] == "2026-03-10T08:00:03"
    assert entry["error"] == ""


def test_log_run_entry_format_with_error(logger_inst, data_dir):
    """log_run() with error arg should persist the error message."""
    logger_inst.log_run(
        task_name="risky-job",
        status="failed",
        started_at="2026-03-10T07:00:00",
        finished_at="2026-03-10T07:00:01",
        error="connection refused",
    )

    line = (data_dir / "cron_runs.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["error"] == "connection refused"
