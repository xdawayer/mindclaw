# input: mindclaw.bus
# output: 消息总线测试
# pos: 消息总线层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import pytest


def test_inbound_message_session_key():
    """session_key 应为 channel:chat_id"""
    from mindclaw.bus.events import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        chat_id="12345",
        user_id="u1",
        username="alice",
        text="hello",
    )
    assert msg.session_key == "telegram:12345"


def test_outbound_message_has_id():
    """OutboundMessage 应自动生成 message_id"""
    from mindclaw.bus.events import OutboundMessage

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="hi")
    assert msg.message_id  # 非空
    assert len(msg.message_id) > 0


@pytest.mark.asyncio
async def test_message_bus_roundtrip():
    """消息应能通过总线往返传递"""
    from mindclaw.bus.events import InboundMessage, OutboundMessage
    from mindclaw.bus.queue import MessageBus

    bus = MessageBus()

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="hi"
    )
    await bus.put_inbound(inbound)
    got = await bus.get_inbound()
    assert got.text == "hi"

    outbound = OutboundMessage(channel="cli", chat_id="local", text="hello!")
    await bus.put_outbound(outbound)
    got = await bus.get_outbound()
    assert got.text == "hello!"


@pytest.mark.asyncio
async def test_message_bus_get_blocks():
    """get_inbound 应阻塞直到有消息"""
    from mindclaw.bus.events import InboundMessage
    from mindclaw.bus.queue import MessageBus

    bus = MessageBus()

    async def delayed_put():
        await asyncio.sleep(0.05)
        await bus.put_inbound(
            InboundMessage(
                channel="cli", chat_id="local", user_id="wzb", username="wzb", text="delayed"
            )
        )

    asyncio.create_task(delayed_put())
    msg = await bus.get_inbound()
    assert msg.text == "delayed"
