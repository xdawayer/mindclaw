# input: mindclaw.tools.message_user, mindclaw.bus
# output: MessageUserTool 测试
# pos: message_user 工具测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest

from mindclaw.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_message_user_sends_outbound():
    """message_user should put an OutboundMessage on the bus."""
    from mindclaw.tools.message_user import MessageUserTool

    bus = MessageBus()
    tool = MessageUserTool(
        bus=bus,
        context_provider=lambda: ("cli", "local"),
    )

    result = await tool.execute({"message": "Working on it..."})

    assert result == "Message sent to user."
    outbound = bus.outbound.get_nowait()
    assert outbound.text == "Working on it..."
    assert outbound.channel == "cli"
    assert outbound.chat_id == "local"


@pytest.mark.asyncio
async def test_message_user_risk_level():
    """message_user should be MODERATE risk level."""
    from mindclaw.tools.base import RiskLevel
    from mindclaw.tools.message_user import MessageUserTool

    bus = MessageBus()
    tool = MessageUserTool(bus=bus)
    assert tool.risk_level == RiskLevel.MODERATE


@pytest.mark.asyncio
async def test_message_user_requires_message_param():
    """message_user should fail gracefully with missing message param."""
    from mindclaw.tools.message_user import MessageUserTool

    bus = MessageBus()
    tool = MessageUserTool(bus=bus, context_provider=lambda: ("cli", "local"))

    with pytest.raises(KeyError):
        await tool.execute({})


@pytest.mark.asyncio
async def test_message_user_context_provider_called_at_execute_time():
    """context_provider should be called at execute time, not init time."""
    from mindclaw.tools.message_user import MessageUserTool

    bus = MessageBus()
    current = ["cli", "local"]
    tool = MessageUserTool(
        bus=bus,
        context_provider=lambda: (current[0], current[1]),
    )

    # Change context before execute
    current[0] = "telegram"
    current[1] = "12345"

    await tool.execute({"message": "Hello from telegram"})

    outbound = bus.outbound.get_nowait()
    assert outbound.channel == "telegram"
    assert outbound.chat_id == "12345"
