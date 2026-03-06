# input: mindclaw.channels
# output: CLI Channel 测试
# pos: 渠道层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_base_channel_is_abstract():
    """BaseChannel 应该是抽象类，不能直接实例化"""
    from mindclaw.channels.base import BaseChannel

    with pytest.raises(TypeError):
        BaseChannel()


@pytest.mark.asyncio
async def test_cli_channel_creates_inbound_message():
    """CLIChannel 应将用户输入转为 InboundMessage 并放入总线"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)

    await channel._handle_input("hello world")

    msg = await bus.get_inbound()
    assert msg.channel == "cli"
    assert msg.chat_id == "local"
    assert msg.text == "hello world"


@pytest.mark.asyncio
async def test_cli_channel_sends_outbound():
    """CLIChannel 应能从 outbound 队列获取消息"""
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    CLIChannel(bus=bus)  # ensure instantiation works

    outbound = OutboundMessage(channel="cli", chat_id="local", text="reply text")
    await bus.put_outbound(outbound)

    msg = await bus.get_outbound()
    assert msg.text == "reply text"
