# input: channels/base.py, bus/events.py, python-telegram-bot, telegram_format.py
# output: 导出 TelegramChannel
# pos: Telegram 渠道实现，使用 polling 模式接收消息，HTML 富文本发送 + 长消息分段 + 重试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from loguru import logger
from telegram import Update
from telegram.constants import ChatAction, MessageLimit
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel
from .telegram_format import markdown_to_telegram_html

# Telegram message text limit (4096 UTF-8 chars)
_MSG_MAX = MessageLimit.MAX_TEXT_LENGTH


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

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    @staticmethod
    def _split_message(text: str) -> list[str]:
        """Split text into chunks that fit Telegram's message size limit.

        Splits on newlines to avoid breaking mid-line.  If a single line
        exceeds the limit, it is split by character boundary.
        """
        if len(text) <= _MSG_MAX:
            return [text]

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for line in text.split("\n"):
            # +1 for the newline separator
            line_len = len(line) + (1 if current else 0)
            if current_len + line_len > _MSG_MAX and current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0

            if len(line) > _MSG_MAX:
                # Flush current buffer first
                if current:
                    chunks.append("\n".join(current))
                    current = []
                    current_len = 0
                # Split oversized line by char
                for i in range(0, len(line), _MSG_MAX):
                    chunks.append(line[i : i + _MSG_MAX])
            else:
                current.append(line)
                current_len += line_len

        if current:
            chunks.append("\n".join(current))
        return chunks

    async def _send_one(self, chat_id: int, text: str) -> None:
        """Send a single chunk with HTML parse_mode, falling back to plain text."""
        html = markdown_to_telegram_html(text)
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=html,
                parse_mode="HTML",
            )
        except Exception:
            logger.debug(
                f"HTML parse_mode failed for chat {chat_id}, retrying as plain text"
            )
            await self._bot.send_message(chat_id=chat_id, text=text)

    async def send(self, msg: OutboundMessage) -> None:
        if self._bot is None:
            logger.warning("TelegramChannel.send() called but bot is not initialized")
            return

        chat_id = int(msg.chat_id)
        chunks = self._split_message(msg.text)
        last_err: Exception | None = None

        for chunk in chunks:
            for attempt in range(3):
                try:
                    await self._send_one(chat_id, chunk)
                    break
                except Exception as exc:
                    last_err = exc
                    logger.warning(
                        f"Telegram send attempt {attempt + 1}/3 failed for "
                        f"chat {chat_id}: {exc}"
                    )
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))
            else:
                logger.exception(
                    f"Failed to send Telegram message to chat {chat_id} "
                    f"after 3 attempts: {last_err}"
                )

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

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

        # Send typing indicator so user knows the bot is processing
        try:
            await self._bot.send_chat_action(
                chat_id=chat.id, action=ChatAction.TYPING
            )
        except Exception:
            pass  # Non-critical, ignore

        await self._handle_message(
            text=message.text,
            chat_id=str(chat.id),
            user_id=str(user.id),
            username=username,
        )
