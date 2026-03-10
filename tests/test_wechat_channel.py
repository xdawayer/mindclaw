# input: mindclaw.channels.wechat_channel
# output: 微信渠道测试
# pos: 验证 WeChatChannel 通过 WebSocket 连接 Node.js Bridge 的消息收发
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

import pytest
import websockets

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


@pytest.fixture
def bus():
    return MessageBus()


@pytest.fixture
async def mock_bridge():
    """Start a mock WeChat bridge WebSocket server."""
    received = []

    async def handler(websocket):
        async for message in websocket:
            data = json.loads(message)
            received.append(data)

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield {"url": f"ws://127.0.0.1:{port}", "received": received, "server": server}
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_wechat_channel_name(bus):
    """WeChatChannel should have name 'wechat'."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999")
    assert ch.name == "wechat"


@pytest.mark.asyncio
async def test_wechat_channel_whitelist(bus):
    """WeChatChannel should respect whitelist."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999", allow_from=["user1"])
    assert ch.is_allowed("user1") is True
    assert ch.is_allowed("user2") is False


@pytest.mark.asyncio
async def test_wechat_handle_message_enqueues(bus):
    """_handle_message should enqueue an InboundMessage."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999")

    await ch._handle_message(
        text="Hello from WeChat",
        chat_id="chat_123",
        user_id="wxid_abc",
        username="Alice",
    )

    msg = await asyncio.wait_for(bus.get_inbound(), timeout=1.0)
    assert msg.channel == "wechat"
    assert msg.text == "Hello from WeChat"
    assert msg.chat_id == "chat_123"
    assert msg.user_id == "wxid_abc"


@pytest.mark.asyncio
async def test_wechat_send_to_bridge(bus, mock_bridge):
    """send() should forward OutboundMessage to the bridge WebSocket."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url=mock_bridge["url"])

    await ch.start()
    # Wait for connection to establish
    await asyncio.sleep(0.1)

    await ch.send(OutboundMessage(
        channel="wechat",
        chat_id="chat_456",
        text="Reply from MindClaw",
    ))

    # Wait for message to be received
    await asyncio.sleep(0.1)
    await ch.stop()

    assert len(mock_bridge["received"]) == 1
    sent = mock_bridge["received"][0]
    assert sent["chat_id"] == "chat_456"
    assert sent["text"] == "Reply from MindClaw"


@pytest.mark.asyncio
async def test_wechat_parse_bridge_message(bus):
    """_parse_bridge_message should extract fields from bridge JSON."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999")

    bridge_msg = {
        "type": "message",
        "chat_id": "room_001",
        "user_id": "wxid_sender",
        "username": "Bob",
        "text": "Test message",
        "is_group": False,
    }

    result = ch._parse_bridge_message(json.dumps(bridge_msg))
    assert result is not None
    assert result["chat_id"] == "room_001"
    assert result["user_id"] == "wxid_sender"
    assert result["text"] == "Test message"


@pytest.mark.asyncio
async def test_wechat_parse_invalid_message(bus):
    """_parse_bridge_message should return None for invalid JSON."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999")

    assert ch._parse_bridge_message("not json") is None
    assert ch._parse_bridge_message('{"type": "heartbeat"}') is None


@pytest.mark.asyncio
async def test_wechat_group_filter(bus):
    """WeChatChannel should filter group messages when allow_groups=False."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    ch = WeChatChannel(bus=bus, bridge_url="ws://localhost:9999", allow_groups=False)

    bridge_msg = {
        "type": "message",
        "chat_id": "room_001",
        "user_id": "wxid_sender",
        "username": "Bob",
        "text": "Group message",
        "is_group": True,
    }

    result = ch._parse_bridge_message(json.dumps(bridge_msg))
    # When allow_groups=False, group messages should be filtered out
    assert result is None


@pytest.mark.asyncio
async def test_wechat_ws_cleared_after_disconnect(bus):
    """BUG FIX: _ws should be set to None after ConnectionClosed so send() logs warning instead of crashing."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    # Start a mock bridge that immediately closes the connection
    async def close_handler(websocket):
        await websocket.close()

    server = await websockets.serve(close_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    ch = WeChatChannel(bus=bus, bridge_url=f"ws://127.0.0.1:{port}")
    await ch.start()

    # Wait for listener to detect ConnectionClosed and clean up
    await asyncio.sleep(0.3)

    # _ws should be None now, so send() should log warning, not crash
    assert ch._ws is None

    await ch.send(OutboundMessage(
        channel="wechat",
        chat_id="chat_123",
        text="Should not crash",
    ))
    # No exception = pass

    await ch.stop()
    server.close()
    await server.wait_closed()


@pytest.mark.asyncio
async def test_wechat_reconnects_after_disconnect(bus):
    """IMPROVEMENT: WeChat channel should auto-reconnect after bridge disconnects."""
    from mindclaw.channels.wechat_channel import WeChatChannel

    connect_count = 0

    async def track_handler(websocket):
        nonlocal connect_count
        connect_count += 1
        if connect_count == 1:
            # First connection: close immediately to trigger reconnect
            await websocket.close()
        else:
            # Second connection: stay open
            try:
                async for _ in websocket:
                    pass
            except websockets.ConnectionClosed:
                pass

    server = await websockets.serve(track_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    ch = WeChatChannel(bus=bus, bridge_url=f"ws://127.0.0.1:{port}", reconnect_delay=0.2)
    await ch.start()

    # Wait for disconnect + reconnect cycle
    await asyncio.sleep(1.0)

    # Should have reconnected
    assert connect_count >= 2, f"Expected reconnect, got {connect_count} connections"
    assert ch._ws is not None, "Should have a live connection after reconnect"

    await ch.stop()
    server.close()
    await server.wait_closed()
