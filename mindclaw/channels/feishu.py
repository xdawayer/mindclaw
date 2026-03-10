# input: lark-oapi, channels/base.py, bus/events.py
# output: 导出 FeishuChannel
# pos: 飞书渠道实现，使用 lark-oapi WebSocket 接收消息
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel


class FeishuChannel(BaseChannel):
    """Feishu (Lark) channel using lark-oapi WebSocket mode."""

    def __init__(
        self,
        bus: MessageBus,
        app_id: str,
        app_secret: str,
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="feishu", bus=bus, allow_from=allow_from)
        self._app_id = app_id
        self._app_secret = app_secret
        self.allow_groups = allow_groups
        self._api_client = None
        self._ws_client = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        import lark_oapi as lark

        self._loop = asyncio.get_running_loop()

        self._api_client = (
            lark.Client.builder().app_id(self._app_id).app_secret(self._app_secret).build()
        )

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_feishu_event)
            .build()
        )

        self._ws_client = lark.ws.Client(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.WARNING,
        )

        # lark ws.Client.start() is blocking, run in executor thread
        self._loop.run_in_executor(None, self._ws_client.start)

    async def stop(self) -> None:
        # lark-oapi ws.Client does not expose a clean stop method
        pass

    async def send(self, msg: OutboundMessage) -> None:
        if self._api_client is None:
            logger.warning("FeishuChannel.send() called but api_client is not initialized")
            return
        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(msg.chat_id)
                    .msg_type("text")
                    .content(json.dumps({"text": msg.text}))
                    .build()
                )
                .build()
            )

            response = await asyncio.to_thread(
                self._api_client.im.v1.message.create, request
            )
            if not response.success():
                logger.error(f"Failed to send Feishu message: {response.msg}")
        except Exception:
            logger.exception(f"Failed to send Feishu message to chat {msg.chat_id}")

    def _on_feishu_event(self, data) -> None:
        """Sync callback from lark-oapi ws thread. Schedules async processing."""
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._process_feishu_message(data),
                self._loop,
            )

    async def _process_feishu_message(self, data) -> None:
        """Process a Feishu message event (async, testable)."""
        try:
            message = data.event.message
            sender = data.event.sender

            chat_type = message.chat_type
            if chat_type == "group" and not self.allow_groups:
                return

            content = json.loads(message.content)
            text = content.get("text", "")
            if not text:
                return

            chat_id = message.chat_id
            user_id = sender.sender_id.open_id

            await self._handle_message(
                text=text,
                chat_id=chat_id,
                user_id=user_id,
                username=user_id,
            )
        except Exception:
            logger.exception("Error handling Feishu message")
