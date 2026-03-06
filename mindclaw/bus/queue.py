# input: asyncio, bus/events.py
# output: 导出 MessageBus
# pos: 消息总线核心，解耦渠道与 Agent
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from .events import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def put_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def get_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def put_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def get_outbound(self) -> OutboundMessage:
        return await self.outbound.get()
