# input: discord.py, channels/base.py, bus/events.py
# output: 导出 DiscordChannel
# pos: Discord 渠道实现，使用 discord.py 库接收/发送消息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

import discord
from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class DiscordChannel(BaseChannel):
    """Discord channel using discord.py (Bot gateway connection)."""

    def __init__(
        self,
        bus: MessageBus,
        token: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="discord", bus=bus, allow_from=allow_from)
        self._token = token
        self.allow_groups = allow_groups

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)
        self._task: asyncio.Task | None = None

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            await self._on_discord_message(message)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._client.start(self._token))

    async def stop(self) -> None:
        if not self._client.is_closed():
            await self._client.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def send(self, msg: OutboundMessage) -> None:
        try:
            channel = self._client.get_channel(int(msg.chat_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(msg.chat_id))
            await channel.send(msg.text)
        except Exception:
            logger.exception(f"Failed to send Discord message to channel {msg.chat_id}")

    async def _on_discord_message(self, message: discord.Message) -> None:
        # Ignore bot's own messages
        if self._client.user is not None and message.author.id == self._client.user.id:
            return

        # Guild (server) vs DM filtering
        if message.guild is not None and not self.allow_groups:
            return

        if not message.content:
            return

        username = message.author.display_name or str(message.author.id)

        await self._handle_message(
            text=message.content,
            chat_id=str(message.channel.id),
            user_id=str(message.author.id),
            username=username,
        )
