# input: mindclaw.security.approval
# output: 审批工作流测试
# pos: 安全层审批机制测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest

from mindclaw.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_approval_granted():
    from mindclaw.security.approval import ApprovalManager
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    async def grant():
        await asyncio.sleep(0.05)
        outbound = await bus.get_outbound()
        assert "exec" in outbound.text
        assert "rm /tmp/test" in outbound.text
        manager.resolve("yes")

    asyncio.create_task(grant())
    result = await manager.request_approval(
        tool_name="exec",
        arguments='{"command": "rm /tmp/test"}',
        channel="cli", chat_id="local",
    )
    assert result is True
    assert not manager.has_pending()


@pytest.mark.asyncio
async def test_approval_rejected():
    from mindclaw.security.approval import ApprovalManager
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    async def reject():
        await asyncio.sleep(0.05)
        await bus.get_outbound()
        manager.resolve("no")

    asyncio.create_task(reject())
    result = await manager.request_approval(
        tool_name="exec",
        arguments='{"command": "rm /tmp/test"}',
        channel="cli", chat_id="local",
    )
    assert result is False
    assert not manager.has_pending()


@pytest.mark.asyncio
async def test_approval_timeout():
    from mindclaw.security.approval import ApprovalManager
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=0.2)

    result = await manager.request_approval(
        tool_name="exec",
        arguments='{"command": "ls"}',
        channel="cli", chat_id="local",
    )
    assert result is False
    request_msg = await bus.get_outbound()
    assert "exec" in request_msg.text
    timeout_msg = await bus.get_outbound()
    assert "timeout" in timeout_msg.text.lower() or "timed out" in timeout_msg.text.lower()


@pytest.mark.asyncio
async def test_has_pending_lifecycle():
    from mindclaw.security.approval import ApprovalManager
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)
    assert not manager.has_pending()

    task = asyncio.create_task(manager.request_approval(
        tool_name="exec", arguments="{}",
        channel="cli", chat_id="local",
    ))
    await asyncio.sleep(0.05)
    assert manager.has_pending()
    manager.resolve("no")
    await task
    assert not manager.has_pending()


@pytest.mark.asyncio
async def test_is_approval_reply_patterns():
    from mindclaw.security.approval import ApprovalManager
    bus = MessageBus()
    manager = ApprovalManager(bus=bus, timeout=5.0)

    # No pending -> nothing is an approval reply
    assert not manager.is_approval_reply("yes")

    task = asyncio.create_task(manager.request_approval(
        tool_name="exec", arguments="{}",
        channel="cli", chat_id="local",
    ))
    await asyncio.sleep(0.05)

    assert manager.is_approval_reply("yes")
    assert manager.is_approval_reply("  YES  ")
    assert manager.is_approval_reply("y")
    assert manager.is_approval_reply("approve")
    assert manager.is_approval_reply("no")
    assert manager.is_approval_reply("n")
    assert manager.is_approval_reply("reject")
    assert not manager.is_approval_reply("hello")
    assert not manager.is_approval_reply("yes please do it")
    assert not manager.is_approval_reply("")

    manager.resolve("n")
    await task


@pytest.mark.asyncio
async def test_approval_approve_variations():
    from mindclaw.security.approval import ApprovalManager
    for word in ("yes", "y", "approve", "YES", "  Y  ", "Approve"):
        bus = MessageBus()
        manager = ApprovalManager(bus=bus, timeout=5.0)

        async def grant(w=word):
            await asyncio.sleep(0.05)
            await bus.get_outbound()
            manager.resolve(w)

        asyncio.create_task(grant())
        result = await manager.request_approval(
            tool_name="exec", arguments="{}",
            channel="cli", chat_id="local",
        )
        assert result is True, f"Expected True for '{word}'"


@pytest.mark.asyncio
async def test_approval_reject_variations():
    from mindclaw.security.approval import ApprovalManager
    for word in ("no", "n", "reject", "NO", "  N  ", "Reject"):
        bus = MessageBus()
        manager = ApprovalManager(bus=bus, timeout=5.0)

        async def reject(w=word):
            await asyncio.sleep(0.05)
            await bus.get_outbound()
            manager.resolve(w)

        asyncio.create_task(reject())
        result = await manager.request_approval(
            tool_name="exec", arguments="{}",
            channel="cli", chat_id="local",
        )
        assert result is False, f"Expected False for '{word}'"
