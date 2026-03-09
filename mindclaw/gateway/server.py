# input: websockets, asyncio, json, mindclaw.gateway.auth
# output: 导出 GatewayServer
# pos: WebSocket 服务器核心，JSON-RPC 2.0 协议处理认证与消息收发
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable, Coroutine
from typing import Any

import websockets
from loguru import logger

from .auth import GatewayAuthManager

# JSON-RPC 2.0 error codes
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_AUTH_FAILED = -32000
ERR_NOT_AUTHENTICATED = -32001


def _jsonrpc_result(result: Any, msg_id: int | str | None) -> str:
    """Build a JSON-RPC 2.0 success response."""
    return json.dumps({"jsonrpc": "2.0", "result": result, "id": msg_id})


def _jsonrpc_error(code: int, message: str, msg_id: int | str | None) -> str:
    """Build a JSON-RPC 2.0 error response."""
    return json.dumps({"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": msg_id})


def _jsonrpc_notification(method: str, params: dict[str, Any]) -> str:
    """Build a JSON-RPC 2.0 notification (no id)."""
    return json.dumps({"jsonrpc": "2.0", "method": method, "params": params})


# Type for on_message callback: can be sync or async
OnMessageCallback = Callable[[str, str], Any] | Callable[[str, str], Coroutine[Any, Any, Any]]


class GatewayServer:
    """WebSocket server with JSON-RPC 2.0 protocol, token auth, and device pairing."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_manager: GatewayAuthManager | None = None,
        on_message: OnMessageCallback | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._auth = auth_manager
        self._on_message = on_message
        self._server: websockets.Server | None = None
        # device_id -> websocket connection
        self._clients: dict[str, websockets.ServerConnection] = {}

    @property
    def port(self) -> int:
        """Actual listening port (useful when constructed with port=0)."""
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await websockets.serve(
            self._handler,
            self._host,
            self._port,
            ping_interval=30,
            ping_timeout=10,
        )
        logger.info(f"Gateway server listening on ws://{self._host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully shut down the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._clients.clear()
            logger.info("Gateway server stopped")

    async def send_to_client(self, device_id: str, data: str) -> bool:
        """Send a raw JSON string to a specific authenticated client.

        Returns True if sent, False if the device is not connected.
        """
        ws = self._clients.get(device_id)
        if ws is None:
            return False
        try:
            await ws.send(data)
            return True
        except websockets.ConnectionClosed:
            self._clients.pop(device_id, None)
            return False

    async def broadcast(self, data: str) -> None:
        """Send a raw JSON string to all authenticated clients."""
        gone: list[str] = []
        for device_id, ws in self._clients.items():
            try:
                await ws.send(data)
            except websockets.ConnectionClosed:
                gone.append(device_id)
        for device_id in gone:
            self._clients.pop(device_id, None)

    # ── internal ──────────────────────────────────────────────

    async def _handler(self, ws: websockets.ServerConnection) -> None:
        """Per-connection handler: authenticate first, then enter message loop."""
        device_id: str | None = None
        try:
            device_id = await self._authenticate(ws)
            if device_id is None:
                return  # auth failed; connection already closed or errored
            self._clients[device_id] = ws
            logger.info(f"Client authenticated: {device_id}")
            await self._message_loop(ws, device_id)
        except websockets.ConnectionClosed:
            logger.debug(f"Client disconnected: {device_id or 'unknown'}")
        finally:
            if device_id:
                self._clients.pop(device_id, None)

    async def _authenticate(self, ws: websockets.ServerConnection) -> str | None:
        """Wait for the first message, which must be an 'auth' JSON-RPC call.

        Returns the device_id on success, or None on failure.
        """
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            return None

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(_jsonrpc_error(ERR_PARSE, "Parse error", None))
            return None

        msg_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})

        if method != "auth":
            await ws.send(_jsonrpc_error(ERR_INVALID_REQUEST, "First message must be 'auth'", msg_id))
            return None

        token = params.get("token", "")
        device_id = params.get("device_id", "")

        if not self._auth or not self._auth.verify_token(token):
            await ws.send(_jsonrpc_error(ERR_AUTH_FAILED, "Authentication failed", msg_id))
            return None

        if not self._auth.is_paired(device_id):
            await ws.send(_jsonrpc_result({"status": "pairing_required"}, msg_id))
            return None

        self._auth.update_last_seen(device_id)
        await ws.send(_jsonrpc_result({"status": "authenticated"}, msg_id))
        return device_id

    async def _message_loop(self, ws: websockets.ServerConnection, device_id: str) -> None:
        """Process messages from an authenticated client."""
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send(_jsonrpc_error(ERR_PARSE, "Parse error", None))
                continue

            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "ping":
                await ws.send(_jsonrpc_result("pong", msg_id))

            elif method == "message":
                text = params.get("text", "")
                if self._on_message:
                    result = self._on_message(device_id, text)
                    if inspect.isawaitable(result):
                        await result
                await ws.send(_jsonrpc_result({"status": "ok"}, msg_id))

            else:
                await ws.send(_jsonrpc_error(ERR_METHOD_NOT_FOUND, f"Unknown method: {method}", msg_id))
