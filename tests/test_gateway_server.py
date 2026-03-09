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
