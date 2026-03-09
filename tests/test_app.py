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
