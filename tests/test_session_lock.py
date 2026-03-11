# input: mindclaw.app, mindclaw.bus.events, mindclaw.config.schema
# output: per-session serialization tests
# pos: TDD regression guard for concurrent same-session message ordering bug
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for per-session serialization to prevent concurrent writes.

Bug: Two messages from the same session dispatched concurrently can read the
same history state and write conflicting responses.

Fix: A per-session asyncio.Lock ensures messages from the same session are
processed sequentially while different sessions run in parallel.
"""

import asyncio

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.config.schema import MindClawConfig


def _make_msg(session: str, text: str) -> InboundMessage:
    """Create an InboundMessage with channel='test' and given chat_id."""
    return InboundMessage(
        channel="test",
        chat_id=session,
        user_id="user1",
        username="alice",
        text=text,
    )


# ---------------------------------------------------------------------------
# Test 1: Bug reproduction — same-session messages run concurrently (RED)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_session_messages_are_serialized():
    """Two messages from the same session must be processed one at a time.

    Without per-session locking both tasks start simultaneously, read the
    same (empty) history, and execute concurrently. The test detects this by
    recording the start/end ordering of each invocation and asserting that
    the second invocation only STARTS after the first one ENDS.
    """
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    order: list[str] = []
    barrier = asyncio.Event()  # used to make the first call block temporarily

    async def slow_handle(msg: InboundMessage) -> None:
        order.append(f"start:{msg.text}")
        if msg.text == "msg1":
            # Block until released so that msg2 would overlap if no lock
            await barrier.wait()
        order.append(f"end:{msg.text}")

    app.agent_loop.handle_message = slow_handle

    msg1 = _make_msg("session-A", "msg1")
    msg2 = _make_msg("session-A", "msg2")

    # Put both messages before starting the router so they arrive together
    await app.bus.put_inbound(msg1)
    await app.bus.put_inbound(msg2)

    router_task = asyncio.create_task(app._message_router())

    # Give the router time to pick up both messages and dispatch
    await asyncio.sleep(0.05)

    # At this point msg1 is blocking. If there is no per-session lock msg2
    # will have already started. Release the barrier.
    barrier.set()

    # Wait for both messages to finish processing
    await asyncio.sleep(0.15)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert len(order) == 4, f"Expected 4 events, got: {order}"

    # msg2 must not start before msg1 ends
    assert order[0] == "start:msg1", f"First event should be start:msg1, got: {order}"
    assert order[1] == "end:msg1", (
        f"msg2 must not start before msg1 ends (no concurrent same-session execution). "
        f"order={order}"
    )
    assert order[2] == "start:msg2", f"Third event should be start:msg2, got: {order}"
    assert order[3] == "end:msg2", f"Fourth event should be end:msg2, got: {order}"


# ---------------------------------------------------------------------------
# Test 2: Different sessions still run in parallel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_different_sessions_run_in_parallel():
    """Messages from different sessions must be processed concurrently.

    If per-session locking serialises ALL messages (not just same-session),
    parallel processing would be lost. This test verifies that two messages
    from different sessions overlap in time.
    """
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    start_times: dict[str, float] = {}
    end_times: dict[str, float] = {}
    started = asyncio.Event()

    async def timed_handle(msg: InboundMessage) -> None:
        import time
        start_times[msg.chat_id] = time.monotonic()
        started.set()
        await asyncio.sleep(0.1)  # simulate work
        end_times[msg.chat_id] = time.monotonic()

    app.agent_loop.handle_message = timed_handle

    msg_a = _make_msg("session-A", "hello from A")
    msg_b = _make_msg("session-B", "hello from B")

    await app.bus.put_inbound(msg_a)
    await app.bus.put_inbound(msg_b)

    router_task = asyncio.create_task(app._message_router())
    # Allow enough time for both to complete
    await asyncio.sleep(0.35)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert "session-A" in start_times, "session-A was never processed"
    assert "session-B" in start_times, "session-B was never processed"

    # The sessions must have overlapped: session-B started before session-A ended
    assert start_times["session-B"] < end_times["session-A"], (
        "Different sessions should run in parallel, but session-B started after "
        f"session-A ended. start_B={start_times['session-B']:.3f}, "
        f"end_A={end_times['session-A']:.3f}"
    )


# ---------------------------------------------------------------------------
# Test 3: Session lock dict is initialised on the app
# ---------------------------------------------------------------------------

def test_app_has_session_locks_dict():
    """MindClawApp must expose _session_locks as a dict for per-session locks."""
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    assert hasattr(app, "_session_locks"), "_session_locks attribute missing"
    assert isinstance(app._session_locks, dict), "_session_locks must be a dict"
    assert len(app._session_locks) == 0, "_session_locks must be empty initially"


# ---------------------------------------------------------------------------
# Test 4: Lock is created per unique session key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_lock_created_per_session():
    """Processing messages for different sessions creates separate lock objects."""
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    processed: list[str] = []

    async def handle(msg: InboundMessage) -> None:
        processed.append(msg.chat_id)

    app.agent_loop.handle_message = handle

    msg_a = _make_msg("session-X", "hello")
    msg_b = _make_msg("session-Y", "world")

    await app.bus.put_inbound(msg_a)
    await app.bus.put_inbound(msg_b)

    router_task = asyncio.create_task(app._message_router())
    await asyncio.sleep(0.15)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert "test:session-X" in app._session_locks, "Lock for test:session-X should exist"
    assert "test:session-Y" in app._session_locks, "Lock for test:session-Y should exist"
    lock_x = app._session_locks["test:session-X"]
    lock_y = app._session_locks["test:session-Y"]
    assert lock_x is not lock_y, "Different sessions must have distinct lock objects"


# ---------------------------------------------------------------------------
# Test 5: Lock key matches InboundMessage.session_key format
# ---------------------------------------------------------------------------

def test_session_key_format():
    """InboundMessage.session_key must be 'channel:chat_id'."""
    msg = _make_msg("room-42", "hi")
    assert msg.session_key == "test:room-42"
