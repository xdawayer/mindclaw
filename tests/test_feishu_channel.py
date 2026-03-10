# input: mindclaw.channels.feishu
# output: FeishuChannel 测试 (mocked)
# pos: 飞书渠道单元测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


def _ensure_lark_oapi_mocked():
    """Ensure lark_oapi modules are available (mocked) for testing."""
    if "lark_oapi" in sys.modules:
        return

    lark_oapi = types.ModuleType("lark_oapi")
    api = types.ModuleType("lark_oapi.api")
    im = types.ModuleType("lark_oapi.api.im")
    v1 = types.ModuleType("lark_oapi.api.im.v1")

    class _Builder:
        @classmethod
        def builder(cls):
            return cls()

        def __getattr__(self, name):
            def method(*args, **kwargs):
                return self
            return method

        def build(self):
            return MagicMock()

    v1.CreateMessageRequest = _Builder
    v1.CreateMessageRequestBody = _Builder

    sys.modules["lark_oapi"] = lark_oapi
    sys.modules["lark_oapi.api"] = api
    sys.modules["lark_oapi.api.im"] = im
    sys.modules["lark_oapi.api.im.v1"] = v1


_ensure_lark_oapi_mocked()


def test_feishu_channel_init():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret", allow_from=["ou_123"])
    assert ch.name == "feishu"
    assert ch.is_allowed("ou_123")
    assert not ch.is_allowed("ou_999")
    assert ch.allow_groups is False


def test_feishu_channel_groups_disabled():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret", allow_groups=False)
    assert ch.allow_groups is False


def test_feishu_channel_groups_enabled():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret", allow_groups=True)
    assert ch.allow_groups is True


@pytest.mark.asyncio
async def test_feishu_on_message_p2p():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret")

    data = MagicMock()
    data.event.message.chat_type = "p2p"
    data.event.message.content = '{"text":"hello from feishu"}'
    data.event.message.chat_id = "oc_123456"
    data.event.sender.sender_id.open_id = "ou_abcdef"

    await ch._process_feishu_message(data)

    msg = await bus.get_inbound()
    assert msg.channel == "feishu"
    assert msg.text == "hello from feishu"
    assert msg.user_id == "ou_abcdef"
    assert msg.chat_id == "oc_123456"


@pytest.mark.asyncio
async def test_feishu_on_message_group_blocked():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret", allow_groups=False)

    data = MagicMock()
    data.event.message.chat_type = "group"
    data.event.message.content = '{"text":"group msg"}'
    data.event.message.chat_id = "oc_123456"
    data.event.sender.sender_id.open_id = "ou_abcdef"

    await ch._process_feishu_message(data)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_feishu_on_message_group_allowed():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret", allow_groups=True)

    data = MagicMock()
    data.event.message.chat_type = "group"
    data.event.message.content = '{"text":"group msg"}'
    data.event.message.chat_id = "oc_123456"
    data.event.sender.sender_id.open_id = "ou_abcdef"

    await ch._process_feishu_message(data)

    msg = await bus.get_inbound()
    assert msg.text == "group msg"


@pytest.mark.asyncio
async def test_feishu_on_message_empty_text():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret")

    data = MagicMock()
    data.event.message.chat_type = "p2p"
    data.event.message.content = '{"text":""}'
    data.event.message.chat_id = "oc_123456"
    data.event.sender.sender_id.open_id = "ou_abcdef"

    await ch._process_feishu_message(data)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_feishu_on_message_whitelist_blocked():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(
        bus=bus, app_id="fake-id", app_secret="fake-secret", allow_from=["ou_allowed"]
    )

    data = MagicMock()
    data.event.message.chat_type = "p2p"
    data.event.message.content = '{"text":"blocked"}'
    data.event.message.chat_id = "oc_123456"
    data.event.sender.sender_id.open_id = "ou_stranger"

    await ch._process_feishu_message(data)
    assert bus.inbound.empty()


@pytest.mark.asyncio
async def test_feishu_send():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret")

    # Build a mock api_client where im.v1.message.create returns a success response
    mock_response = MagicMock()
    mock_response.success.return_value = True
    mock_create = MagicMock(return_value=mock_response)

    ch._api_client = MagicMock()
    ch._api_client.im.v1.message.create = mock_create

    msg = OutboundMessage(channel="feishu", chat_id="oc_123456", text="reply text")
    await ch.send(msg)

    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_feishu_send_no_client():
    from mindclaw.channels.feishu import FeishuChannel

    bus = MessageBus()
    ch = FeishuChannel(bus=bus, app_id="fake-id", app_secret="fake-secret")
    # _api_client is None by default
    msg = OutboundMessage(channel="feishu", chat_id="oc_123456", text="reply text")
    await ch.send(msg)  # Should not raise
