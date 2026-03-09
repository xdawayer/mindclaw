# input: mindclaw.channels
# output: BaseChannel + CLIChannel 测试
# pos: 渠道层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_base_channel_is_abstract():
    from mindclaw.channels.base import BaseChannel

    with pytest.raises(TypeError):
        BaseChannel(name="test", bus=MessageBus())


def test_base_channel_is_allowed_no_whitelist():
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    ch = DummyChannel(name="dummy", bus=MessageBus(), allow_from=None)
    assert ch.is_allowed("anyone") is True


def test_base_channel_is_allowed_with_whitelist():
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    ch = DummyChannel(name="dummy", bus=MessageBus(), allow_from=["user1", "user2"])
    assert ch.is_allowed("user1") is True
    assert ch.is_allowed("user3") is False


@pytest.mark.asyncio
async def test_base_channel_handle_message_allowed():
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    bus = MessageBus()
    ch = DummyChannel(name="test", bus=bus)
    await ch._handle_message(text="hello", chat_id="c1", user_id="u1", username="alice")
    msg = await bus.get_inbound()
    assert msg.channel == "test"
    assert msg.text == "hello"
    assert msg.user_id == "u1"


@pytest.mark.asyncio
async def test_base_channel_handle_message_blocked():
    from mindclaw.channels.base import BaseChannel

    class DummyChannel(BaseChannel):
        async def start(self): pass
        async def stop(self): pass
        async def send(self, msg): pass

    bus = MessageBus()
    ch = DummyChannel(name="test", bus=bus, allow_from=["user1"])
    await ch._handle_message(text="hello", chat_id="c1", user_id="bad_user", username="bob")
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_cli_channel_creates_inbound_message():
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)
    assert channel.name == "cli"

    await channel._handle_input("hello world")

    msg = await bus.get_inbound()
    assert msg.channel == "cli"
    assert msg.chat_id == "local"
    assert msg.text == "hello world"


@pytest.mark.asyncio
async def test_cli_channel_send():
    from mindclaw.channels.cli_channel import CLIChannel

    bus = MessageBus()
    channel = CLIChannel(bus=bus)
    outbound = OutboundMessage(channel="cli", chat_id="local", text="reply text")
    await channel.send(outbound)
