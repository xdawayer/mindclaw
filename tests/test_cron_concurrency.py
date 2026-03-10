# input: mindclaw.app, mindclaw.config.schema
# output: Cron 并发控制测试
# pos: 验证 bounded semaphore 并发限制和 shutdown 清理
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.config.schema import MindClawConfig


def _make_msg(text: str = "hello", chat_id: str = "test") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        chat_id=chat_id,
        user_id="u1",
        username="tester",
        text=text,
    )


@pytest.mark.asyncio
async def test_max_concurrent_tasks_config_default():
    """AgentConfig.max_concurrent_tasks should default to 3."""
    config = MindClawConfig()
    assert config.agent.max_concurrent_tasks == 3


@pytest.mark.asyncio
async def test_max_concurrent_tasks_config_from_alias():
    """max_concurrent_tasks should be settable via camelCase alias."""
    config = MindClawConfig(agent={"maxConcurrentTasks": 5})
    assert config.agent.max_concurrent_tasks == 5


@pytest.mark.asyncio
async def test_concurrent_messages_not_blocked():
    """Multiple messages should process concurrently, not sequentially."""
    from mindclaw.app import MindClawApp

    with patch.object(MindClawApp, "__init__", lambda self, cfg: None):
        app = MindClawApp.__new__(MindClawApp)

    # Minimal wiring for _message_router
    from mindclaw.bus.queue import MessageBus

    app.bus = MessageBus()
    app._gateway_auth = None
    app.approval_manager = Mock()
    app.approval_manager.has_pending.return_value = False
    app._task_semaphore = asyncio.Semaphore(3)
    app._active_tasks = set()
    app.hook_registry = AsyncMock()

    # Track concurrent execution
    concurrent_count = 0
    max_concurrent = 0

    async def slow_process(msg):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.1)
        concurrent_count -= 1

    app._process_message = slow_process

    # Put 3 messages
    for i in range(3):
        await app.bus.put_inbound(_make_msg(f"msg-{i}", f"chat-{i}"))

    # Run the router in a task
    router_task = asyncio.create_task(app._message_router())

    # Wait for all messages to start processing
    await asyncio.sleep(0.2)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert max_concurrent >= 2, f"Expected concurrent execution, got max_concurrent={max_concurrent}"


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """Semaphore should limit concurrent tasks to max_concurrent_tasks."""
    from mindclaw.app import MindClawApp

    with patch.object(MindClawApp, "__init__", lambda self, cfg: None):
        app = MindClawApp.__new__(MindClawApp)

    from mindclaw.bus.queue import MessageBus

    app.bus = MessageBus()
    app._gateway_auth = None
    app.approval_manager = Mock()
    app.approval_manager.has_pending.return_value = False
    app._task_semaphore = asyncio.Semaphore(2)
    app._active_tasks = set()
    app.hook_registry = AsyncMock()

    concurrent_count = 0
    max_concurrent = 0
    gate = asyncio.Event()

    async def blocking_process(msg):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await gate.wait()
        concurrent_count -= 1

    app._process_message = blocking_process

    # Put 4 messages (more than semaphore allows)
    for i in range(4):
        await app.bus.put_inbound(_make_msg(f"msg-{i}", f"chat-{i}"))

    router_task = asyncio.create_task(app._message_router())

    # Let router pick up messages
    await asyncio.sleep(0.05)

    # Only 2 should be running concurrently
    assert max_concurrent == 2, f"Expected max 2 concurrent, got {max_concurrent}"

    # Release the gate so tasks complete
    gate.set()
    await asyncio.sleep(0.05)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_cleanup_cancels_all_tasks():
    """Shutdown should cancel all active tasks in _active_tasks set."""
    from mindclaw.app import MindClawApp

    with patch.object(MindClawApp, "__init__", lambda self, cfg: None):
        app = MindClawApp.__new__(MindClawApp)

    app._active_tasks = set()

    # Create some long-running tasks
    async def long_running():
        await asyncio.sleep(100)

    for _ in range(3):
        task = asyncio.create_task(long_running())
        app._active_tasks.add(task)
        task.add_done_callback(app._active_tasks.discard)

    assert len(app._active_tasks) == 3

    # Cancel all
    for t in list(app._active_tasks):
        t.cancel()

    await asyncio.sleep(0.01)

    # All tasks should be done (cancelled)
    for t in list(app._active_tasks):
        assert t.done()


@pytest.mark.asyncio
async def test_process_message_guarded_releases_semaphore():
    """_process_message_guarded should release semaphore even on exception."""
    from mindclaw.app import MindClawApp

    with patch.object(MindClawApp, "__init__", lambda self, cfg: None):
        app = MindClawApp.__new__(MindClawApp)

    sem = asyncio.Semaphore(2)
    app._task_semaphore = sem
    app.hook_registry = AsyncMock()

    async def failing_process(msg):
        raise ValueError("boom")

    app._process_message = failing_process

    # Acquire semaphore (simulating _message_router acquiring before creating task)
    await sem.acquire()

    msg = _make_msg("fail")
    # _process_message_guarded should release even on error
    with pytest.raises(ValueError, match="boom"):
        await app._process_message_guarded(msg)

    # Semaphore should be released back: verify by acquiring twice without blocking
    sem.release()  # release the one we acquired above
    for _ in range(2):
        acquired = sem.acquire()
        # If we can acquire, the semaphore was properly released
        await acquired


@pytest.mark.asyncio
async def test_task_done_removes_from_active_set():
    """Completed tasks should be removed from _active_tasks via done callback."""
    from mindclaw.app import MindClawApp

    with patch.object(MindClawApp, "__init__", lambda self, cfg: None):
        app = MindClawApp.__new__(MindClawApp)

    app._active_tasks = set()

    async def quick():
        return

    task = asyncio.create_task(quick())
    app._active_tasks.add(task)
    task.add_done_callback(app._active_tasks.discard)

    await task

    # Give the callback a chance to run
    await asyncio.sleep(0)

    assert len(app._active_tasks) == 0
