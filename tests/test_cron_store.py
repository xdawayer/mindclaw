# input: mindclaw.orchestrator.cron_store
# output: CronTaskStore 共享单例测试
# pos: 验证 cron 任务持久化层的 CRUD、原子写入、并发安全
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

import pytest


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def store(data_dir):
    from mindclaw.orchestrator.cron_store import CronTaskStore

    return CronTaskStore(data_dir=data_dir)


def _make_task(name: str = "test-task", cron_expr: str = "0 9 * * *", action: str = "Do thing") -> dict:
    return {
        "name": name,
        "cron_expr": cron_expr,
        "action": action,
        "created_at": "2026-03-10T10:00:00",
        "last_run": None,
        "enabled": True,
    }


# ── Basic CRUD ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_add_and_load(store, data_dir):
    """add() should persist a task, load() should return it."""
    task = _make_task("daily-news")
    await store.add("cron_abc", task)

    tasks = await store.load()
    assert "cron_abc" in tasks
    assert tasks["cron_abc"]["name"] == "daily-news"

    # File should exist on disk
    assert (data_dir / "cron_tasks.json").exists()


@pytest.mark.asyncio
async def test_store_load_empty(store):
    """load() should return empty dict when no tasks file."""
    tasks = await store.load()
    assert tasks == {}


@pytest.mark.asyncio
async def test_store_get(store):
    """get() should return a single task by ID, or None."""
    await store.add("cron_1", _make_task("task-1"))

    task = await store.get("cron_1")
    assert task is not None
    assert task["name"] == "task-1"

    missing = await store.get("nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_store_remove(store):
    """remove() should delete a task and return it."""
    await store.add("cron_rm", _make_task("to-remove"))

    removed = await store.remove("cron_rm")
    assert removed is not None
    assert removed["name"] == "to-remove"

    tasks = await store.load()
    assert "cron_rm" not in tasks


@pytest.mark.asyncio
async def test_store_remove_nonexistent(store):
    """remove() should return None for nonexistent ID."""
    removed = await store.remove("nope")
    assert removed is None


@pytest.mark.asyncio
async def test_store_update_last_run(store):
    """update_last_run() should set the last_run timestamp."""
    await store.add("cron_lr", _make_task("track-run"))

    await store.update_last_run("cron_lr", "2026-03-10T12:00:00")

    task = await store.get("cron_lr")
    assert task is not None
    assert task["last_run"] == "2026-03-10T12:00:00"


@pytest.mark.asyncio
async def test_store_update_last_run_nonexistent(store):
    """update_last_run() should silently skip nonexistent ID."""
    # Should not raise
    await store.update_last_run("nope", "2026-03-10T12:00:00")


# ── Enabled/disabled ────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_set_enabled(store):
    """set_enabled() should toggle the enabled field."""
    await store.add("cron_en", _make_task("toggle-me"))

    await store.set_enabled("cron_en", False)
    task = await store.get("cron_en")
    assert task is not None
    assert task["enabled"] is False

    await store.set_enabled("cron_en", True)
    task = await store.get("cron_en")
    assert task is not None
    assert task["enabled"] is True


@pytest.mark.asyncio
async def test_store_set_enabled_nonexistent(store):
    """set_enabled() should silently skip nonexistent ID."""
    await store.set_enabled("nope", False)


# ── Atomic write ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_atomic_write(store, data_dir):
    """Writes should be atomic (via .tmp + rename), no partial content."""
    await store.add("cron_aw", _make_task("atomic-test"))

    # Read file and verify it's valid JSON
    content = (data_dir / "cron_tasks.json").read_text(encoding="utf-8")
    tasks = json.loads(content)
    assert "cron_aw" in tasks

    # No .tmp file should remain
    tmp_files = list(data_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


# ── Concurrent access ────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_concurrent_add(store, data_dir):
    """Two concurrent add() calls should not corrupt the file."""

    async def add_task(task_id: str, name: str):
        await store.add(task_id, _make_task(name))

    await asyncio.gather(
        add_task("cron_c1", "concurrent-1"),
        add_task("cron_c2", "concurrent-2"),
    )

    tasks = await store.load()
    assert "cron_c1" in tasks
    assert "cron_c2" in tasks

    # File must be valid JSON
    content = (data_dir / "cron_tasks.json").read_text(encoding="utf-8")
    json.loads(content)  # Should not raise


@pytest.mark.asyncio
async def test_store_concurrent_add_and_remove(store):
    """Concurrent add and remove should not corrupt state."""
    await store.add("cron_keep", _make_task("keep-me"))
    await store.add("cron_drop", _make_task("drop-me"))

    await asyncio.gather(
        store.add("cron_new", _make_task("new-one")),
        store.remove("cron_drop"),
    )

    tasks = await store.load()
    assert "cron_keep" in tasks
    assert "cron_new" in tasks
    assert "cron_drop" not in tasks


# ── Returns copy, not mutable reference ──────────────────────


@pytest.mark.asyncio
async def test_store_add_if_name_unique(store):
    """add_if_name_unique() should reject duplicate names atomically."""
    task_a = _make_task("unique-name")
    task_b = _make_task("unique-name")

    added_first = await store.add_if_name_unique("cron_a", task_a)
    assert added_first is True

    added_second = await store.add_if_name_unique("cron_b", task_b)
    assert added_second is False

    tasks = await store.load()
    assert len(tasks) == 1
    assert "cron_a" in tasks


@pytest.mark.asyncio
async def test_store_read_non_dict_json(store, data_dir):
    """_read() should handle non-dict JSON gracefully."""
    (data_dir / "cron_tasks.json").write_text("[]", encoding="utf-8")
    tasks = await store.load()
    assert tasks == {}


@pytest.mark.asyncio
async def test_store_load_returns_copy(store):
    """load() should return a copy -- mutations should not affect store."""
    await store.add("cron_im", _make_task("immutable"))

    tasks = await store.load()
    tasks["cron_im"]["name"] = "MUTATED"

    reloaded = await store.load()
    assert reloaded["cron_im"]["name"] == "immutable"
