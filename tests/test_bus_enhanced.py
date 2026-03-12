# input: mindclaw.bus.queue, mindclaw.bus.events
# output: 消息去重和限流测试
# pos: 消息总线增强功能测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus


def _make_inbound(
    text: str = "hello",
    channel: str = "cli",
    chat_id: str = "local",
    user_id: str = "wzb",
) -> InboundMessage:
    return InboundMessage(
        channel=channel,
        chat_id=chat_id,
        user_id=user_id,
        username=user_id,
        text=text,
    )


# ── Dedup tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_dedup_blocks_identical_message_within_window():
    """Same channel+chat_id+text within 5s should be deduplicated."""
    bus = MessageBus()

    msg1 = _make_inbound("hello")
    msg2 = _make_inbound("hello")

    accepted1 = await bus.put_inbound_dedup(msg1)
    accepted2 = await bus.put_inbound_dedup(msg2)

    assert accepted1 is True
    assert accepted2 is False
    assert bus.inbound.qsize() == 1


@pytest.mark.asyncio
async def test_dedup_allows_different_text():
    """Different text should NOT be deduplicated."""
    bus = MessageBus()

    msg1 = _make_inbound("hello")
    msg2 = _make_inbound("world")

    accepted1 = await bus.put_inbound_dedup(msg1)
    accepted2 = await bus.put_inbound_dedup(msg2)

    assert accepted1 is True
    assert accepted2 is True
    assert bus.inbound.qsize() == 2


@pytest.mark.asyncio
async def test_dedup_allows_different_channel():
    """Same text from different channels should NOT be deduplicated."""
    bus = MessageBus()

    msg1 = _make_inbound("hello", channel="cli")
    msg2 = _make_inbound("hello", channel="telegram")

    accepted1 = await bus.put_inbound_dedup(msg1)
    accepted2 = await bus.put_inbound_dedup(msg2)

    assert accepted1 is True
    assert accepted2 is True


@pytest.mark.asyncio
async def test_dedup_allows_after_window_expires():
    """Same message after 5s window should be accepted."""
    bus = MessageBus(dedup_window=0.1)  # 100ms window for testing

    msg1 = _make_inbound("hello")
    accepted1 = await bus.put_inbound_dedup(msg1)
    assert accepted1 is True

    await asyncio.sleep(0.15)

    msg2 = _make_inbound("hello")
    accepted2 = await bus.put_inbound_dedup(msg2)
    assert accepted2 is True


# ── Rate limit tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_allows_under_limit():
    """Messages under rate limit should be accepted."""
    bus = MessageBus(rate_limit=5, rate_window=60.0)

    for i in range(5):
        accepted = await bus.put_inbound_rated(_make_inbound(f"msg{i}"))
        assert accepted is True

    assert bus.inbound.qsize() == 5


@pytest.mark.asyncio
async def test_rate_limit_rejects_over_limit():
    """Messages over rate limit should be rejected."""
    bus = MessageBus(rate_limit=3, rate_window=60.0)

    results = []
    for i in range(5):
        accepted = await bus.put_inbound_rated(_make_inbound(f"msg{i}"))
        results.append(accepted)

    assert results == [True, True, True, False, False]
    assert bus.inbound.qsize() == 3


@pytest.mark.asyncio
async def test_rate_limit_per_session():
    """Rate limits should be per session_key (channel:chat_id)."""
    bus = MessageBus(rate_limit=2, rate_window=60.0)

    # Session 1: cli:local
    a1 = await bus.put_inbound_rated(_make_inbound("msg1", channel="cli", chat_id="local"))
    a2 = await bus.put_inbound_rated(_make_inbound("msg2", channel="cli", chat_id="local"))
    a3 = await bus.put_inbound_rated(_make_inbound("msg3", channel="cli", chat_id="local"))

    # Session 2: telegram:123
    b1 = await bus.put_inbound_rated(_make_inbound("msg1", channel="telegram", chat_id="123"))
    b2 = await bus.put_inbound_rated(_make_inbound("msg2", channel="telegram", chat_id="123"))

    assert [a1, a2, a3] == [True, True, False]
    assert [b1, b2] == [True, True]


@pytest.mark.asyncio
async def test_rate_limit_resets_after_window():
    """Rate limit should reset after the window expires."""
    bus = MessageBus(rate_limit=2, rate_window=0.1)  # 100ms window

    await bus.put_inbound_rated(_make_inbound("msg1"))
    await bus.put_inbound_rated(_make_inbound("msg2"))
    rejected = await bus.put_inbound_rated(_make_inbound("msg3"))
    assert rejected is False

    await asyncio.sleep(0.15)

    accepted = await bus.put_inbound_rated(_make_inbound("msg4"))
    assert accepted is True
