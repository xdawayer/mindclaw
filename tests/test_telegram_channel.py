# input: mindclaw.channels.telegram, mindclaw.channels.telegram_format
# output: TelegramChannel + telegram_format 测试 (mocked)
# pos: Telegram 渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

# ------------------------------------------------------------------
# Channel init tests
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Receiving tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_on_message_private():
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake", allow_from=None)

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


# ------------------------------------------------------------------
# Sending tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_send_html():
    """send() should use parse_mode=HTML for rich formatting."""
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")
    ch._bot = AsyncMock()

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="**bold** text")
    await ch.send(msg)

    call_kwargs = ch._bot.send_message.call_args
    assert call_kwargs.kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_telegram_send_html_fallback_plain():
    """If HTML parse fails, send() should fallback to plain text."""
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")

    mock_bot = AsyncMock()
    # First call (HTML) raises, second call (plain) succeeds
    mock_bot.send_message.side_effect = [
        Exception("Bad Request: can't parse entities"),
        None,
    ]
    ch._bot = mock_bot

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="broken <html")
    await ch.send(msg)

    assert mock_bot.send_message.call_count == 2
    second_call = mock_bot.send_message.call_args_list[1]
    assert "parse_mode" not in second_call.kwargs


@pytest.mark.asyncio
async def test_telegram_send_retry():
    """send() should retry up to 3 times on failure."""
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")

    mock_bot = AsyncMock()
    # Fail twice (both HTML and plain each time), succeed on 3rd attempt
    mock_bot.send_message.side_effect = [
        Exception("network error"),  # attempt 1 HTML
        Exception("network error"),  # attempt 1 plain fallback
        Exception("network error"),  # attempt 2 HTML
        Exception("network error"),  # attempt 2 plain fallback
        None,                        # attempt 3 HTML succeeds
    ]
    ch._bot = mock_bot

    msg = OutboundMessage(channel="telegram", chat_id="12345", text="hello")
    await ch.send(msg)

    # 2 calls per failed attempt (HTML + fallback) + 1 successful = 5
    assert mock_bot.send_message.call_count == 5


@pytest.mark.asyncio
async def test_telegram_send_long_message_split():
    """Messages exceeding 4096 chars should be split into chunks."""
    from mindclaw.channels.telegram import TelegramChannel

    bus = MessageBus()
    ch = TelegramChannel(bus=bus, token="fake")
    ch._bot = AsyncMock()

    # Create a message > 4096 chars
    long_text = "A" * 5000
    msg = OutboundMessage(channel="telegram", chat_id="12345", text=long_text)
    await ch.send(msg)

    # Should be split into 2 chunks
    assert ch._bot.send_message.call_count == 2


# ------------------------------------------------------------------
# Message splitting tests
# ------------------------------------------------------------------


def test_split_message_short():
    from mindclaw.channels.telegram import TelegramChannel

    chunks = TelegramChannel._split_message("short text")
    assert chunks == ["short text"]


def test_split_message_long():
    from mindclaw.channels.telegram import TelegramChannel

    text = "line\n" * 2000  # ~10000 chars
    chunks = TelegramChannel._split_message(text)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 4096


def test_split_message_single_long_line():
    from mindclaw.channels.telegram import TelegramChannel

    text = "X" * 8000
    chunks = TelegramChannel._split_message(text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 4096
    assert len(chunks[1]) == 3904


# ------------------------------------------------------------------
# Format conversion tests
# ------------------------------------------------------------------


def test_markdown_to_telegram_html_bold():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("**bold**") == "<b>bold</b>"


def test_markdown_to_telegram_html_italic():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("*italic*") == "<i>italic</i>"


def test_markdown_to_telegram_html_strike():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("~~strike~~") == "<s>strike</s>"


def test_markdown_to_telegram_html_link():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    result = markdown_to_telegram_html("[click](https://example.com)")
    assert result == '<a href="https://example.com">click</a>'


def test_markdown_to_telegram_html_inline_code():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("`code`") == "<code>code</code>"


def test_markdown_to_telegram_html_code_block():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    text = "```python\nprint('hi')\n```"
    result = markdown_to_telegram_html(text)
    assert '<code class="language-python">' in result
    assert "print(&#x27;hi&#x27;)" in result or "print('hi')" in result


def test_markdown_to_telegram_html_heading():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("# Title") == "<b>Title</b>"
    assert markdown_to_telegram_html("## Subtitle") == "<b>Subtitle</b>"


def test_markdown_to_telegram_html_escape():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    result = markdown_to_telegram_html("a < b & c > d")
    assert "&lt;" in result
    assert "&amp;" in result
    assert "&gt;" in result


def test_markdown_to_telegram_html_empty():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    assert markdown_to_telegram_html("") == ""


def test_markdown_to_telegram_html_mixed():
    from mindclaw.channels.telegram_format import markdown_to_telegram_html

    text = "**bold** and *italic* with `code`"
    result = markdown_to_telegram_html(text)
    assert "<b>bold</b>" in result
    assert "<i>italic</i>" in result
    assert "<code>code</code>" in result
