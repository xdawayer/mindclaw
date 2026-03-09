# input: mindclaw.gateway
# output: GatewayServer + GatewayChannel 测试
# pos: Gateway 层集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
import time

import pytest
import websockets

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus


@pytest.mark.asyncio
async def test_gateway_server_auth_success(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.server import GatewayServer

    messages_received = []

    async def on_message(device_id, text):
        messages_received.append((device_id, text))

    auth = GatewayAuthManager(token="test-token", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=on_message,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "test-token", "device_id": "dev1"}, "id": 1
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"]["status"] == "authenticated"

            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "message",
                "params": {"text": "hello"}, "id": 2
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"]["status"] == "ok"

        await asyncio.sleep(0.1)
        assert ("dev1", "hello") in messages_received
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_server_auth_wrong_token(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="correct", paired_devices_path=tmp_path / "d.json")
    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "wrong", "device_id": "dev1"}, "id": 1
            }))
            resp = json.loads(await ws.recv())
            assert "error" in resp
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_server_ping_pong(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "t", "device_id": "dev1"}, "id": 1
            }))
            await ws.recv()

            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "ping", "id": 99
            }))
            resp = json.loads(await ws.recv())
            assert resp["result"] == "pong"
            assert resp["id"] == 99
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_unpaired_device_gets_pairing_flow(tmp_path):
    """BUG#4: Unpaired device must trigger actual pairing workflow."""
    from mindclaw.gateway.auth import GatewayAuthManager
    from mindclaw.gateway.server import GatewayServer

    async def on_message(device_id, text):
        pass

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    # No paired devices — dev1 is unpaired

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=on_message,
    )
    await server.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {
                    "token": "t",
                    "device_id": "new_dev",
                    "device_name": "New Phone",
                }, "id": 1
            }))
            resp = json.loads(await ws.recv())

            # Should get pairing_required with a pairing_id
            assert resp.get("result", {}).get("status") == "pairing_required"
            pairing_id = resp.get("result", {}).get("pairing_id")
            assert pairing_id is not None, \
                "Server must return a pairing_id so the device can track the pairing flow"

            # The pairing request should now be pending in auth manager
            assert pairing_id in auth._pending_pairings, \
                "A PairingRequest should be created in auth manager"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_channel_no_broadcast_fallback(tmp_path):
    """BUG#3: Targeted send to offline device must NOT broadcast to all clients."""
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.channel import GatewayChannel
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test1", time.time(), time.time())
    auth._paired["dev2"] = PairedDevice("dev2", "Test2", time.time(), time.time())

    bus = MessageBus()
    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    channel = GatewayChannel(bus=bus, server=server)
    await channel.start()
    port = server.port

    try:
        # Connect only dev2 (dev1 is offline)
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws2:
            await ws2.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "t", "device_id": "dev2"}, "id": 1
            }))
            await ws2.recv()

            # Send message targeted at dev1 (offline)
            out = OutboundMessage(channel="gateway", chat_id="dev1", text="secret for dev1")
            await channel.send(out)

            # dev2 should NOT receive dev1's message
            try:
                msg = await asyncio.wait_for(ws2.recv(), timeout=0.5)
                data = json.loads(msg)
                # If we get here, broadcast leak occurred
                assert False, \
                    f"dev2 received dev1's message via broadcast fallback: {data}"
            except asyncio.TimeoutError:
                pass  # Correct: dev2 did not receive dev1's message
    finally:
        await channel.stop()


@pytest.mark.asyncio
async def test_reconnection_preserves_new_connection(tmp_path):
    """BUG#5: When device reconnects, old connection cleanup must not remove new connection."""
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    await server.start()
    port = server.port

    try:
        # Connect first time
        ws1 = await websockets.connect(f"ws://127.0.0.1:{port}")
        await ws1.send(json.dumps({
            "jsonrpc": "2.0", "method": "auth",
            "params": {"token": "t", "device_id": "dev1"}, "id": 1
        }))
        resp = json.loads(await ws1.recv())
        assert resp["result"]["status"] == "authenticated"

        # Connect second time (reconnection)
        ws2 = await websockets.connect(f"ws://127.0.0.1:{port}")
        await ws2.send(json.dumps({
            "jsonrpc": "2.0", "method": "auth",
            "params": {"token": "t", "device_id": "dev1"}, "id": 1
        }))
        resp = json.loads(await ws2.recv())
        assert resp["result"]["status"] == "authenticated"

        # Close old connection (triggers finally block cleanup)
        await ws1.close()
        await asyncio.sleep(0.2)  # Let cleanup happen

        # New connection should still be in _clients
        assert "dev1" in server._clients, \
            "New connection was removed by old connection's cleanup"

        # Verify new connection still works
        sent = await server.send_to_client(
            "dev1",
            json.dumps({"jsonrpc": "2.0", "method": "test", "params": {"text": "hello"}})
        )
        assert sent is True, "send_to_client should succeed with new connection"

        await ws2.close()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_channel_send(tmp_path):
    from mindclaw.gateway.auth import GatewayAuthManager, PairedDevice
    from mindclaw.gateway.channel import GatewayChannel
    from mindclaw.gateway.server import GatewayServer

    auth = GatewayAuthManager(token="t", paired_devices_path=tmp_path / "d.json")
    auth._paired["dev1"] = PairedDevice("dev1", "Test", time.time(), time.time())

    bus = MessageBus()
    server = GatewayServer(
        host="127.0.0.1", port=0, auth_manager=auth,
        on_message=lambda d, t: None,
    )
    channel = GatewayChannel(bus=bus, server=server)
    await channel.start()
    port = server.port

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "jsonrpc": "2.0", "method": "auth",
                "params": {"token": "t", "device_id": "dev1"}, "id": 1
            }))
            await ws.recv()

            out = OutboundMessage(channel="gateway", chat_id="dev1", text="reply!")
            await channel.send(out)

            resp = json.loads(await ws.recv())
            assert resp["method"] == "reply"
            assert resp["params"]["text"] == "reply!"
    finally:
        await channel.stop()
