# input: asyncio, channels/base.py, bus/queue.py, bus/events.py
# output: 导出 ChannelManager
# pos: 渠道管理器，负责渠道生命周期和出站消息分发
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class ChannelManager:
    """Manages channel lifecycle and outbound message dispatch."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel
        logger.info(f"Channel registered: {channel.name}")

    async def start_all(self) -> None:
        if not self._channels:
            return
        await asyncio.gather(*(ch.start() for ch in self._channels.values()))

    async def stop_all(self) -> None:
        for name, ch in self._channels.items():
            try:
                await ch.stop()
            except Exception:
                logger.exception(f"Error stopping channel {name}")

    async def dispatch_outbound(self, msg: OutboundMessage) -> None:
        ch = self._channels.get(msg.channel)
        if ch is None:
            logger.warning(f"No channel found for outbound message: {msg.channel}")
            return
        await ch.send(msg)

    def get(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)
