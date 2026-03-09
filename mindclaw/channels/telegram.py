# input: channels/base.py, bus/events.py, python-telegram-bot
# output: 导出 TelegramChannel
# pos: Telegram 渠道实现，使用 polling 模式接收消息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from loguru import logger
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class TelegramChannel(BaseChannel):
    """Telegram channel using python-telegram-bot (polling mode)."""

    def __init__(
        self,
        bus: MessageBus,
        token: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="telegram", bus=bus, allow_from=allow_from)
        self._token = token
        self.allow_groups = allow_groups
        self._app = None
        self._bot = None

    async def start(self) -> None:
        self._app = ApplicationBuilder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        await self._app.initialize()
        self._bot = self._app.bot
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, msg: OutboundMessage) -> None:
        if self._bot is None:
            logger.warning("TelegramChannel.send() called but bot is not initialized")
            return
        try:
            await self._bot.send_message(
                chat_id=int(msg.chat_id),
                text=msg.text,
            )
        except Exception:
            logger.exception(f"Failed to send Telegram message to chat {msg.chat_id}")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat

        if message is None or user is None or chat is None:
            return

        if not message.text:
            return

        # Group filter
        if chat.type != "private" and not self.allow_groups:
            return

        username = user.username or user.first_name or str(user.id)

        await self._handle_message(
            text=message.text,
            chat_id=str(chat.id),
            user_id=str(user.id),
            username=username,
        )
