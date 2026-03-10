# input: mindclaw.channels.discord_channel
# output: DiscordChannel 测试 (mocked)
# pos: Discord 渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

discord = pytest.importorskip("discord")


def test_discord_channel_init():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake-token", allow_from=["123"])
    assert ch.name == "discord"
    assert ch.is_allowed("123")
    assert not ch.is_allowed("999")
    assert ch.allow_groups is False


def test_discord_channel_groups_disabled():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake-token", allow_groups=False)
    assert ch.allow_groups is False


def test_discord_channel_groups_enabled():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake-token", allow_groups=True)
    assert ch.allow_groups is True


def _mock_client(ch):
    """Replace the real discord.Client with a MagicMock (user property is read-only)."""
    mock = MagicMock()
    mock.user.id = 99999
    ch._client = mock


@pytest.mark.asyncio
async def test_discord_on_message_dm():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake", allow_from=None)
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 12345
    message.author.display_name = "alice"
    message.content = "hello from discord"
    message.channel.id = 67890
    message.guild = None

    await ch._on_discord_message(message)

    msg = await bus.get_inbound()
    assert msg.channel == "discord"
    assert msg.text == "hello from discord"
    assert msg.user_id == "12345"
    assert msg.chat_id == "67890"


@pytest.mark.asyncio
async def test_discord_on_message_guild_blocked():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake", allow_groups=False)
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 12345
    message.content = "guild msg"
    message.channel.id = 67890
    message.guild = MagicMock()

    await ch._on_discord_message(message)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_discord_on_message_guild_allowed():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake", allow_groups=True)
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 12345
    message.author.display_name = "bob"
    message.content = "guild msg"
    message.channel.id = 67890
    message.guild = MagicMock()

    await ch._on_discord_message(message)

    msg = await bus.get_inbound()
    assert msg.text == "guild msg"


@pytest.mark.asyncio
async def test_discord_on_message_bot_ignored():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake")
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 99999  # Same as bot
    message.content = "bot message"
    message.guild = None

    await ch._on_discord_message(message)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_discord_on_message_empty_content():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake")
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 12345
    message.content = ""
    message.guild = None

    await ch._on_discord_message(message)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_discord_on_message_whitelist_blocked():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake", allow_from=["111"])
    _mock_client(ch)

    message = MagicMock()
    message.author.id = 222
    message.author.display_name = "stranger"
    message.content = "blocked"
    message.channel.id = 67890
    message.guild = None

    await ch._on_discord_message(message)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_discord_send():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake")

    mock_channel = AsyncMock()
    ch._client.get_channel = MagicMock(return_value=mock_channel)

    msg = OutboundMessage(channel="discord", chat_id="67890", text="reply text")
    await ch.send(msg)

    ch._client.get_channel.assert_called_once_with(67890)
    mock_channel.send.assert_awaited_once_with("reply text")


@pytest.mark.asyncio
async def test_discord_send_fetch_fallback():
    from mindclaw.channels.discord_channel import DiscordChannel

    bus = MessageBus()
    ch = DiscordChannel(bus=bus, token="fake")

    mock_channel = AsyncMock()
    ch._client.get_channel = MagicMock(return_value=None)
    ch._client.fetch_channel = AsyncMock(return_value=mock_channel)

    msg = OutboundMessage(channel="discord", chat_id="67890", text="reply text")
    await ch.send(msg)

    ch._client.fetch_channel.assert_awaited_once_with(67890)
    mock_channel.send.assert_awaited_once_with("reply text")
