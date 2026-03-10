# input: mindclaw.channels.slack
# output: SlackChannel 测试 (mocked)
# pos: Slack 渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def _ensure_slack_sdk_mocked():
    """Ensure slack_sdk modules are available (mocked) for testing."""
    if "slack_sdk" in sys.modules:
        return
    slack_sdk = types.ModuleType("slack_sdk")
    socket_mode = types.ModuleType("slack_sdk.socket_mode")
    response_mod = types.ModuleType("slack_sdk.socket_mode.response")

    class SocketModeResponse:
        def __init__(self, envelope_id: str) -> None:
            self.envelope_id = envelope_id

    response_mod.SocketModeResponse = SocketModeResponse
    socket_mode.response = response_mod
    slack_sdk.socket_mode = socket_mode

    sys.modules["slack_sdk"] = slack_sdk
    sys.modules["slack_sdk.socket_mode"] = socket_mode
    sys.modules["slack_sdk.socket_mode.response"] = response_mod


_ensure_slack_sdk_mocked()


def test_slack_channel_init():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake", allow_from=["U123"])
    assert ch.name == "slack"
    assert ch.is_allowed("U123")
    assert not ch.is_allowed("U999")
    assert ch.allow_groups is False


def test_slack_channel_groups_disabled():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake", allow_groups=False)
    assert ch.allow_groups is False


def test_slack_channel_groups_enabled():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake", allow_groups=True)
    assert ch.allow_groups is True


@pytest.mark.asyncio
async def test_slack_on_event_dm():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "text": "hello from slack",
            "user": "U12345",
            "channel": "D67890",
            "channel_type": "im",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)

    msg = await bus.get_inbound()
    assert msg.channel == "slack"
    assert msg.text == "hello from slack"
    assert msg.user_id == "U12345"
    assert msg.chat_id == "D67890"


@pytest.mark.asyncio
async def test_slack_on_event_channel_blocked():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake", allow_groups=False)

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "text": "channel msg",
            "user": "U12345",
            "channel": "C67890",
            "channel_type": "channel",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_slack_on_event_channel_allowed():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake", allow_groups=True)

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "text": "channel msg",
            "user": "U12345",
            "channel": "C67890",
            "channel_type": "channel",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)

    msg = await bus.get_inbound()
    assert msg.text == "channel msg"


@pytest.mark.asyncio
async def test_slack_on_event_subtype_ignored():
    """Messages with subtype (bot_message, channel_join, etc.) should be ignored."""
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "subtype": "bot_message",
            "text": "bot said something",
            "user": "U12345",
            "channel": "D67890",
            "channel_type": "im",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_slack_on_event_empty_text():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "text": "",
            "user": "U12345",
            "channel": "D67890",
            "channel_type": "im",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_slack_on_event_non_message_ignored():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "reaction_added",
            "user": "U12345",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_slack_on_event_ack_sent():
    """Socket Mode events must be acknowledged."""
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")

    req = MagicMock()
    req.type = "events_api"
    req.envelope_id = "envelope-123"
    req.payload = {
        "event": {
            "type": "message",
            "text": "hello",
            "user": "U12345",
            "channel": "D67890",
            "channel_type": "im",
        }
    }

    client = AsyncMock()
    await ch._on_socket_event(client, req)

    client.send_socket_mode_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_slack_send_plain_text():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")
    ch._web_client = AsyncMock()

    msg = OutboundMessage(channel="slack", chat_id="C67890", text="reply text")
    await ch.send(msg)

    ch._web_client.chat_postMessage.assert_awaited_once_with(
        channel="C67890",
        text="reply text",
    )


@pytest.mark.asyncio
async def test_slack_send_converts_markdown():
    """send() should convert standard Markdown to Slack mrkdwn format."""
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")
    ch._web_client = AsyncMock()

    msg = OutboundMessage(
        channel="slack",
        chat_id="C67890",
        text="**bold** and [link](https://example.com)",
    )
    await ch.send(msg)

    call_kwargs = ch._web_client.chat_postMessage.call_args.kwargs
    sent_text = call_kwargs["text"]
    # **bold** should become *bold* in Slack mrkdwn
    assert "**bold**" not in sent_text
    assert "*bold*" in sent_text
    # [link](url) should become <url|link> in Slack mrkdwn
    assert "<https://example.com|link>" in sent_text


@pytest.mark.asyncio
async def test_slack_send_no_client():
    from mindclaw.channels.slack import SlackChannel

    bus = MessageBus()
    ch = SlackChannel(bus=bus, app_token="xapp-fake", bot_token="xoxb-fake")
    # _web_client is None by default
    msg = OutboundMessage(channel="slack", chat_id="C67890", text="reply text")
    await ch.send(msg)  # Should not raise
