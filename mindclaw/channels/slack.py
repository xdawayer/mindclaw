# input: slack-sdk, channels/base.py, bus/events.py
# output: 导出 SlackChannel
# pos: Slack 渠道实现，使用 Socket Mode (WebSocket) 接收消息，通过 Block Kit markdown block 发送
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel
from .slack_format import markdown_to_slack

# Slack section block text limit (3000 chars per text object)
_SECTION_TEXT_MAX = 3000


class SlackChannel(BaseChannel):
    """Slack channel using Socket Mode (no public HTTP endpoint needed)."""

    def __init__(
        self,
        bus: MessageBus,
        app_token: str,
        bot_token: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="slack", bus=bus, allow_from=allow_from)
        self._app_token = app_token
        self._bot_token = bot_token
        self.allow_groups = allow_groups
        self._web_client = None
        self._socket_client = None

    async def start(self) -> None:
        from slack_sdk.socket_mode.aiohttp import SocketModeClient
        from slack_sdk.web.async_client import AsyncWebClient

        self._web_client = AsyncWebClient(token=self._bot_token)
        self._socket_client = SocketModeClient(
            app_token=self._app_token,
            web_client=self._web_client,
        )
        self._socket_client.socket_mode_request_listeners.append(self._on_socket_event)
        await self._socket_client.connect()

    async def stop(self) -> None:
        if self._socket_client:
            await self._socket_client.disconnect()
        if self._web_client and self._web_client.session:
            await self._web_client.session.close()

    @staticmethod
    def _build_blocks(text: str) -> list[dict]:
        """Convert text to Slack section blocks with mrkdwn formatting.

        Slack section text objects have a 3000-char limit, so long messages
        are split into multiple section blocks.
        """
        mrkdwn = markdown_to_slack(text)
        if len(mrkdwn) <= _SECTION_TEXT_MAX:
            return [{"type": "section", "text": {"type": "mrkdwn", "text": mrkdwn}}]
        blocks: list[dict] = []
        remaining = mrkdwn
        while remaining:
            chunk = remaining[:_SECTION_TEXT_MAX]
            remaining = remaining[_SECTION_TEXT_MAX:]
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
        return blocks

    async def send(self, msg: OutboundMessage) -> None:
        if self._web_client is None:
            logger.warning("SlackChannel.send() called but web_client is not initialized")
            return
        blocks = self._build_blocks(msg.text)
        # text= is required as fallback for notifications/search
        plain_fallback = msg.text[:300] if len(msg.text) > 300 else msg.text
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                await self._web_client.chat_postMessage(
                    channel=msg.chat_id,
                    text=plain_fallback,
                    blocks=blocks,
                )
                return
            except Exception as exc:
                last_err = exc
                logger.warning(
                    f"Slack send attempt {attempt + 1}/3 failed for "
                    f"channel {msg.chat_id}: {exc}"
                )
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
        logger.exception(
            f"Failed to send Slack message to channel {msg.chat_id} "
            f"after 3 attempts: {last_err}"
        )

    async def _on_socket_event(self, client, req) -> None:
        from slack_sdk.socket_mode.response import SocketModeResponse

        if req.type != "events_api":
            return

        # Acknowledge the event
        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_socket_mode_response(response)

        event = req.payload.get("event", {})

        # Only handle plain user messages (no subtype = no bot_message, channel_join, etc.)
        if event.get("type") != "message" or "subtype" in event:
            return

        # Ignore messages from bots (including our own)
        if event.get("bot_id") or event.get("bot_profile"):
            return

        text = event.get("text", "")
        user_id = event.get("user", "")

        if not text or not user_id:
            return

        # Channel type filtering: "im" = DM, others = public/private channels
        channel_type = event.get("channel_type", "")
        if channel_type != "im" and not self.allow_groups:
            return

        channel_id = event.get("channel", "")

        await self._handle_message(
            text=text,
            chat_id=channel_id,
            user_id=user_id,
            username=user_id,
        )
