# input: mindclaw.channels.manager
# output: ChannelManager 测试
# pos: 渠道管理器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.base import BaseChannel


class FakeChannel(BaseChannel):
    def __init__(self, name: str, bus: MessageBus):
        super().__init__(name=name, bus=bus)
        self.started = False
        self.stopped = False
        self.sent: list[OutboundMessage] = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, msg: OutboundMessage):
        self.sent.append(msg)


def test_channel_manager_register_and_get():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel("test", bus)
    mgr.register(ch)
    assert mgr.get("test") is ch
    assert mgr.get("nonexistent") is None


@pytest.mark.asyncio
async def test_channel_manager_start_stop_all():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch1 = FakeChannel("a", bus)
    ch2 = FakeChannel("b", bus)
    mgr.register(ch1)
    mgr.register(ch2)

    await mgr.start_all()
    assert ch1.started and ch2.started

    await mgr.stop_all()
    assert ch1.stopped and ch2.stopped


@pytest.mark.asyncio
async def test_channel_manager_dispatch_outbound():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    ch = FakeChannel("telegram", bus)
    mgr.register(ch)

    msg = OutboundMessage(channel="telegram", chat_id="123", text="hello")
    await mgr.dispatch_outbound(msg)
    assert len(ch.sent) == 1
    assert ch.sent[0].text == "hello"


@pytest.mark.asyncio
async def test_channel_manager_dispatch_unknown_channel():
    from mindclaw.channels.manager import ChannelManager

    bus = MessageBus()
    mgr = ChannelManager(bus)
    msg = OutboundMessage(channel="nonexistent", chat_id="123", text="hello")
    await mgr.dispatch_outbound(msg)
