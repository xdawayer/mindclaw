# input: tools/base.py, bus/queue.py, bus/events.py
# output: 导出 MessageUserTool
# pos: 主动发消息给用户的工具，允许 Agent 在推理过程中向用户发送中间状态
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

from collections.abc import Callable

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

from .base import RiskLevel, Tool


class MessageUserTool(Tool):
    """Send a proactive message to the user during agent processing."""

    name = "message_user"
    description = "Send a message to the user. Use for status updates or intermediate results."
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message text to send to the user",
            },
        },
        "required": ["message"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(
        self,
        bus: MessageBus,
        context_provider: Callable[[], tuple[str, str]] = lambda: ("", ""),
    ) -> None:
        self._bus = bus
        self._context_provider = context_provider

    async def execute(self, params: dict) -> str:
        text = params["message"]
        channel, chat_id = self._context_provider()
        outbound = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            text=text,
        )
        await self._bus.put_outbound(outbound)
        return "Message sent to user."
