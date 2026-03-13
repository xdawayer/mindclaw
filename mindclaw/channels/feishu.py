# input: lark-oapi (optional), httpx, channels/base.py, bus/events.py
# output: 导出 FeishuChannel
# pos: 飞书渠道实现，支持 lark-oapi SDK 模式 (双向) 和 Webhook 模式 (推送卡片)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
import time

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import BaseChannel

# ── Constants ──────────────────────────────────────────────

_MAX_CARD_BYTES = 28_000  # 飞书限制 30KB，留 2KB 余量


# ── Card Builder ───────────────────────────────────────────


def _escape_lark(text: str) -> str:
    """Escape Lark Markdown special characters."""
    return text.replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")


def _md_to_lark(text: str) -> str:
    """Convert standard Markdown to Feishu lark_md format.

    Feishu lark_md differences:
    - No ## headers → convert to **bold**
    - No > blockquotes → convert to italic
    - **bold** and *italic* work
    - [link](url) works
    - - list items work
    - `code` works
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip()
        # Convert headers to bold
        if stripped.startswith("### "):
            line = "**" + stripped[4:].strip() + "**"
        elif stripped.startswith("## "):
            line = "**" + stripped[3:].strip() + "**"
        elif stripped.startswith("# "):
            line = "**" + stripped[2:].strip() + "**"
        # Convert blockquotes to text
        elif stripped.startswith("> "):
            line = "*" + stripped[2:].strip() + "*"
        result.append(line)
    return "\n".join(result)


def _build_card(title: str, content: str, template: str = "blue") -> dict:
    """Build a Feishu interactive card from markdown content.

    Splits into multiple cards if content exceeds size limit.
    """
    header = {
        "title": {"tag": "plain_text", "content": title},
        "template": template,
    }

    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    footer = {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"MindClaw | {timestamp}"}],
    }

    # Split content into sections by ## headers, then convert to lark_md
    sections = [_md_to_lark(s) for s in _split_sections(content)]

    elements: list[dict] = []
    for section in sections:
        if elements:
            elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": section},
        })

    elements.append({"tag": "hr"})
    elements.append(footer)

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": header,
            "elements": elements,
        },
    }

    # Check size, truncate if needed
    card_bytes = len(json.dumps(card, ensure_ascii=False).encode("utf-8"))
    if card_bytes > _MAX_CARD_BYTES:
        return _build_truncated_card(header, sections, footer)

    return card


def _split_sections(content: str) -> list[str]:
    """Split markdown content by ## headers into sections."""
    lines = content.split("\n")
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("## ") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current).strip())

    # Filter empty sections
    return [s for s in sections if s.strip()]


def _build_truncated_card(
    header: dict, sections: list[str], footer: dict
) -> dict:
    """Build a card that fits within size limit by truncating sections."""
    elements: list[dict] = []

    for section in sections:
        if elements:
            elements.append({"tag": "hr"})

        # Progressively truncate until it fits
        truncated = section
        while len(truncated.encode("utf-8")) > 3000:
            truncated = truncated[:int(len(truncated) * 0.8)] + "\n..."

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": truncated},
        })

        # Check total size
        test_card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": header,
                "elements": [*elements, {"tag": "hr"}, footer],
            },
        }
        if len(json.dumps(test_card, ensure_ascii=False).encode("utf-8")) > _MAX_CARD_BYTES:
            # Remove last element and stop
            elements.pop()
            if elements and elements[-1].get("tag") == "hr":
                elements.pop()
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "... [内容过长，已截断]"},
            })
            break

    elements.append({"tag": "hr"})
    elements.append(footer)

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": header,
            "elements": elements,
        },
    }


# ── Channel ────────────────────────────────────────────────


class FeishuChannel(BaseChannel):
    """Feishu (Lark) channel.

    Supports two modes:
    - **SDK mode** (app_id + app_secret): bidirectional via lark-oapi WebSocket
    - **Webhook mode** (webhook_url): one-way push with interactive cards
    """

    def __init__(
        self,
        bus: MessageBus,
        app_id: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        allow_from: list[str] | None = None,
        allow_groups: bool = False,
    ) -> None:
        super().__init__(name="feishu", bus=bus, allow_from=allow_from)
        self._app_id = app_id
        self._app_secret = app_secret
        self._webhook_url = webhook_url
        self.allow_groups = allow_groups
        self._api_client = None
        self._ws_client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._use_sdk = bool(app_id and app_secret)

    async def start(self) -> None:
        if not self._use_sdk:
            logger.info("FeishuChannel started in webhook-only mode")
            return

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
        # Determine webhook URL: chat_id as URL override, or default webhook
        webhook_url = ""
        if msg.chat_id and msg.chat_id.startswith("https://"):
            webhook_url = msg.chat_id
        elif self._webhook_url:
            webhook_url = self._webhook_url

        if webhook_url:
            await self._send_webhook(msg, webhook_url)
        elif self._api_client is not None:
            await self._send_sdk(msg)
        else:
            logger.warning("FeishuChannel.send() called but no webhook_url or api_client available")

    async def _send_webhook(self, msg: OutboundMessage, webhook_url: str) -> None:
        """Send message via webhook as interactive card."""
        import httpx

        # Extract title from first line of text, or use default
        title = "MindClaw"
        content = msg.text
        lines = content.strip().split("\n")
        if lines and lines[0].startswith("# "):
            title = lines[0].lstrip("# ").strip()
            content = "\n".join(lines[1:]).strip()

        card = _build_card(title, content)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    webhook_url,
                    json=card,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                body = resp.json()
                if body.get("code") != 0:
                    logger.error("Feishu webhook error: {} (code={})", body.get("msg"), body.get("code"))
                else:
                    logger.info("Feishu card sent via webhook")
        except Exception:
            logger.exception("Failed to send Feishu webhook message")

    async def _send_sdk(self, msg: OutboundMessage) -> None:
        """Send message via lark-oapi SDK (interactive card if long, text if short)."""
        try:
            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            # Short messages as text, long ones as card
            if len(msg.text) < 500:
                msg_type = "text"
                content_str = json.dumps({"text": msg.text})
            else:
                title = "MindClaw"
                text = msg.text
                lines = text.strip().split("\n")
                if lines and lines[0].startswith("# "):
                    title = lines[0].lstrip("# ").strip()
                    text = "\n".join(lines[1:]).strip()

                card_data = _build_card(title, text)
                msg_type = "interactive"
                content_str = json.dumps(card_data["card"])

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(msg.chat_id)
                    .msg_type(msg_type)
                    .content(content_str)
                    .build()
                )
                .build()
            )

            response = await asyncio.to_thread(
                self._api_client.im.v1.message.create, request
            )
            if not response.success():
                logger.error("Failed to send Feishu message: {}", response.msg)
        except Exception:
            logger.exception("Failed to send Feishu message to chat {}", msg.chat_id)

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
