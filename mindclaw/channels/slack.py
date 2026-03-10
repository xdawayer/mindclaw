# input: slack-sdk, channels/base.py, bus/events.py, channels/slack_format.py
# output: 导出 SlackChannel
# pos: Slack 渠道实现，使用 Socket Mode (WebSocket) 接收消息，发送时自动转换 Markdown → Slack mrkdwn
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel
from .slack_format import markdown_to_slack


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

    async def send(self, msg: OutboundMessage) -> None:
        if self._web_client is None:
            logger.warning("SlackChannel.send() called but web_client is not initialized")
            return
        try:
            await self._web_client.chat_postMessage(
                channel=msg.chat_id,
                text=markdown_to_slack(msg.text),
            )
        except Exception:
            logger.exception(f"Failed to send Slack message to channel {msg.chat_id}")

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
