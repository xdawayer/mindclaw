# input: channels/base.py, websockets, json
# output: 导出 WeChatChannel
# pos: 微信渠道，通过 WebSocket 连接 Node.js Bridge 收发消息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""WeChat channel via Node.js Bridge WebSocket connection."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets
from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel

_RECONNECT_DELAY = 5.0  # seconds between reconnect attempts


class WeChatChannel(BaseChannel):
    """WeChat channel that connects to a Node.js bridge via WebSocket."""

    def __init__(
        self,
        bus: MessageBus,
        bridge_url: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
        reconnect_delay: float = _RECONNECT_DELAY,
    ) -> None:
        super().__init__(name="wechat", bus=bus, allow_from=allow_from)
        self._bridge_url = bridge_url
        self.allow_groups = allow_groups
        self._ws: Any = None
        self._listener_task: asyncio.Task | None = None
        self._reconnect_delay = reconnect_delay
        self._stopped = False

    async def start(self) -> None:
        self._stopped = False
        await self._connect()
        self._listener_task = asyncio.create_task(self._run_with_reconnect())

    async def _connect(self) -> bool:
        """Attempt to connect to the bridge. Returns True on success."""
        try:
            self._ws = await websockets.connect(self._bridge_url)
            logger.info(f"WeChat bridge connected: {self._bridge_url}")
            return True
        except Exception:
            logger.warning(f"Failed to connect to WeChat bridge: {self._bridge_url}")
            self._ws = None
            return False

    async def stop(self) -> None:
        self._stopped = True
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WeChat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if not self._ws:
            logger.warning("WeChat bridge not connected, cannot send message")
            return

        payload = json.dumps({
            "type": "send",
            "chat_id": msg.chat_id,
            "text": msg.text,
        })
        await self._ws.send(payload)

    def _parse_bridge_message(self, raw: str) -> dict | None:
        """Parse a JSON message from the bridge. Returns None if invalid or filtered."""
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        if data.get("type") != "message":
            return None

        # Filter group messages if not allowed
        if data.get("is_group") and not self.allow_groups:
            return None

        required = ("chat_id", "user_id", "text")
        if not all(k in data for k in required):
            return None

        return data

    async def _run_with_reconnect(self) -> None:
        """Run listen loop with auto-reconnect on disconnect."""
        while not self._stopped:
            if self._ws:
                await self._listen()
            if self._stopped:
                break
            logger.info(f"WeChat reconnecting in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            await self._connect()

    async def _listen(self) -> None:
        """Listen for messages from the bridge WebSocket."""
        try:
            async for raw in self._ws:
                parsed = self._parse_bridge_message(raw)
                if parsed is None:
                    continue

                await self._handle_message(
                    text=parsed["text"],
                    chat_id=parsed["chat_id"],
                    user_id=parsed["user_id"],
                    username=parsed.get("username", parsed["user_id"]),
                )
            # Clean close — loop exited normally
            logger.warning("WeChat bridge connection closed")
            self._ws = None
        except websockets.ConnectionClosed:
            logger.warning("WeChat bridge connection closed unexpectedly")
            self._ws = None
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WeChat listener error")
            self._ws = None
