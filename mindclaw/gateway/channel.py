# input: mindclaw.channels.base.BaseChannel, mindclaw.gateway.server.GatewayServer
# output: 导出 GatewayChannel
# pos: Gateway 渠道适配器，将 GatewayServer 接入 BaseChannel 体系
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.channels.base import BaseChannel

from .server import GatewayServer, _jsonrpc_notification


class GatewayChannel(BaseChannel):
    """Thin adapter: bridges GatewayServer WebSocket connections to the MessageBus."""

    def __init__(
        self,
        bus: MessageBus,
        server: GatewayServer,
        allow_from: list[str] | None = None,
    ) -> None:
        super().__init__(name="gateway", bus=bus, allow_from=allow_from)
        self._server = server

    async def start(self) -> None:
        """Start the underlying WebSocket server."""
        await self._server.start()
        logger.info("GatewayChannel started")

    async def stop(self) -> None:
        """Stop the underlying WebSocket server."""
        await self._server.stop()
        logger.info("GatewayChannel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send an outbound message to a specific device or broadcast.

        If msg.chat_id matches a connected device_id, send only to that device.
        Otherwise broadcast to all authenticated clients.
        """
        payload = _jsonrpc_notification("reply", {"text": msg.text})

        if msg.chat_id:
            sent = await self._server.send_to_client(msg.chat_id, payload)
            if not sent:
                # Fall back to broadcast if target device not connected
                await self._server.broadcast(payload)
        else:
            await self._server.broadcast(payload)
