# input: mindclaw.app
# output: MindClawApp 编排器测试
# pos: 顶层编排器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.config.schema import MindClawConfig


def test_app_instantiation():
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)
    assert app.bus is not None
    assert app.channel_manager is not None
    assert app.agent_loop is not None
    assert app.approval_manager is not None


def test_app_register_tools():
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)
    app._register_tools()
    # Should have at least the basic tools
    assert app.tool_registry.get("read_file") is not None
    assert app.tool_registry.get("list_dir") is not None


@pytest.mark.asyncio
async def test_app_outbound_routing():
    """Outbound messages should be dispatched to the right channel."""
    from mindclaw.app import MindClawApp
    from mindclaw.channels.base import BaseChannel

    class FakeChannel(BaseChannel):
        def __init__(self, bus):
            super().__init__(name="fake", bus=bus)
            self.sent = []

        async def start(self):
            pass

        async def stop(self):
            pass

        async def send(self, msg):
            self.sent.append(msg)

    config = MindClawConfig()
    app = MindClawApp(config)
    fake_ch = FakeChannel(app.bus)
    app.channel_manager.register(fake_ch)

    # Put outbound message
    out = OutboundMessage(channel="fake", chat_id="c1", text="hello")
    await app.bus.put_outbound(out)

    # Run outbound router briefly
    router_task = asyncio.create_task(app._outbound_router())
    await asyncio.sleep(0.1)
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert len(fake_ch.sent) == 1
    assert fake_ch.sent[0].text == "hello"


@pytest.mark.asyncio
async def test_app_message_router_dispatches_to_agent():
    """Normal messages should be dispatched to the agent loop."""
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    handled = []

    async def mock_handle(msg):
        handled.append(msg)

    app.agent_loop.handle_message = mock_handle

    # Put inbound message
    inbound = InboundMessage(
        channel="cli",
        chat_id="local",
        user_id="u1",
        username="alice",
        text="hi",
    )
    await app.bus.put_inbound(inbound)

    router_task = asyncio.create_task(app._message_router())
    await asyncio.sleep(0.1)
    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    assert len(handled) == 1
    assert handled[0].text == "hi"


@pytest.mark.asyncio
async def test_approval_reply_must_match_channel_and_chat():
    """BUG#2: Approval reply from wrong channel/chat_id must be ignored."""
    from mindclaw.app import MindClawApp

    config = MindClawConfig()
    app = MindClawApp(config)

    async def mock_handle(msg):
        pass

    app.agent_loop.handle_message = mock_handle

    # Request approval on channel="cli", chat_id="local"
    request_task = asyncio.create_task(
        app.approval_manager.request_approval(
            tool_name="exec",
            arguments="rm -rf /",
            channel="cli",
            chat_id="local",
        )
    )
    await asyncio.sleep(0.05)  # Let the approval request be created

    # Send approval reply from WRONG channel (telegram, different chat_id)
    wrong_channel_msg = InboundMessage(
        channel="telegram",
        chat_id="attacker-chat",
        user_id="attacker",
        username="mallory",
        text="yes",
    )
    await app.bus.put_inbound(wrong_channel_msg)

    # Run the message router briefly
    router_task = asyncio.create_task(app._message_router())
    await asyncio.sleep(0.1)

    # The approval should still be pending (not resolved by wrong channel)
    assert app.approval_manager.has_pending(), \
        "Approval from wrong channel should be ignored, approval should still be pending"

    # Now send from correct channel
    correct_msg = InboundMessage(
        channel="cli",
        chat_id="local",
        user_id="u1",
        username="alice",
        text="yes",
    )
    await app.bus.put_inbound(correct_msg)
    await asyncio.sleep(0.1)

    router_task.cancel()
    try:
        await router_task
    except asyncio.CancelledError:
        pass

    result = await asyncio.wait_for(request_task, timeout=1.0)
    assert result is True, "Approval from correct channel should be accepted"
