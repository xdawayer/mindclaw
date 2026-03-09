# input: mindclaw.channels.telegram
# output: TelegramChannel 测试 (mocked)
# pos: Telegram 渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def test_telegram_channel_init():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_from=["123"])
    assert ch.name == "telegram"
    assert ch.is_allowed("123")
    assert not ch.is_allowed("999")
    assert ch.allow_groups is False


def test_telegram_channel_groups_disabled():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_groups=False)
    assert ch.allow_groups is False


def test_telegram_channel_groups_enabled():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake-token", allow_groups=True)
    assert ch.allow_groups is True


@pytest.mark.asyncio
async def test_telegram_on_message_private():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_from=None)

    # Simulate a Telegram Update
    update = MagicMock()
    update.effective_message.text = "hello from telegram"
    update.effective_user.id = 12345
    update.effective_user.username = "alice"
    update.effective_user.first_name = "Alice"
    update.effective_chat.id = 12345
    update.effective_chat.type = "private"

    context = MagicMock()
    await ch._on_message(update, context)

    msg = await bus.get_inbound()
    assert msg.channel == "telegram"
    assert msg.text == "hello from telegram"
    assert msg.user_id == "12345"
    assert msg.chat_id == "12345"


@pytest.mark.asyncio
async def test_telegram_on_message_group_blocked():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_groups=False)

    update = MagicMock()
    update.effective_message.text = "group msg"
    update.effective_user.id = 12345
    update.effective_chat.id = -100123
    update.effective_chat.type = "group"

    context = MagicMock()
    await ch._on_message(update, context)

    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_telegram_on_message_group_allowed():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_groups=True)

    update = MagicMock()
    update.effective_message.text = "group msg"
    update.effective_user.id = 12345
    update.effective_user.username = "bob"
    update.effective_user.first_name = "Bob"
    update.effective_chat.id = -100123
    update.effective_chat.type = "group"

    context = MagicMock()
    await ch._on_message(update, context)

    msg = await bus.get_inbound()
    assert msg.text == "group msg"


@pytest.mark.asyncio
async def test_telegram_send():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")
    ch._bot = AsyncMock()

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="reply text")
    await ch.send(msg)

    ch._bot.send_message.assert_awaited_once_with(
        chat_id=12345,
        text="reply text",
        parse_mode="Markdown",
    )
