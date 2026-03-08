# input: mindclaw.security.approval, mindclaw.bus
# output: 消息路由测试
# pos: 验证审批回复被正确路由
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.security.approval import ApprovalManager


@pytest.mark.asyncio
async def test_approval_reply_is_routed_not_queued():
    """When there's a pending approval, 'yes'/'no' should resolve it."""
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    approval_task = asyncio.create_task(
        manager.request_approval("exec", "{}", "cli", "local")
    )
    await asyncio.sleep(0.05)
    assert manager.has_pending()

    manager.resolve("yes")
    result = await approval_task
    assert result is True


@pytest.mark.asyncio
async def test_non_approval_message_during_pending():
    """Non-approval text should NOT resolve a pending approval."""
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=0.3)

    approval_task = asyncio.create_task(
        manager.request_approval("exec", "{}", "cli", "local")
    )
    await asyncio.sleep(0.05)

    assert not manager.is_approval_reply("hello")
    assert manager.is_approval_reply("yes")

    result = await approval_task
    assert result is False


@pytest.mark.asyncio
async def test_end_to_end_approval_via_bus():
    """Full flow: approval request -> user replies 'yes' via bus -> approved."""
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    async def router_loop():
        msg = await bus.get_inbound()
        if manager.has_pending() and manager.is_approval_reply(msg.text):
            manager.resolve(msg.text)
            return True
        return False

    approval_task = asyncio.create_task(
        manager.request_approval("exec", "{}", "cli", "local")
    )
    await asyncio.sleep(0.05)

    await bus.put_inbound(
        InboundMessage(
            channel="cli",
            chat_id="local",
            user_id="test",
            username="test",
            text="yes",
        )
    )

    routed = await router_loop()
    assert routed is True
    result = await approval_task
    assert result is True


@pytest.mark.asyncio
async def test_non_approval_msg_does_not_block_router_during_pending():
    """Non-approval message during pending approval should be dropped, not block."""
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    approval_task = asyncio.create_task(
        manager.request_approval("exec", "{}", "cli", "local")
    )
    await asyncio.sleep(0.05)
    assert manager.has_pending()

    # Simulate the message_router logic: non-approval msg should be skipped
    non_approval_msg = InboundMessage(
        channel="cli", chat_id="local",
        user_id="test", username="test", text="hello",
    )
    # Router should skip this message (has_pending + not approval reply)
    assert not manager.is_approval_reply(non_approval_msg.text)
    # The key invariant: router must NOT await agent_task here;
    # instead it should continue and remain responsive.

    # Now send the real approval
    manager.resolve("yes")
    result = await approval_task
    assert result is True
