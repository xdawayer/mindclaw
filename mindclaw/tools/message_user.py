# input: tools/base.py, bus/queue.py, bus/events.py, orchestrator/agent_loop (context vars)
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
        context_provider: Callable[[], tuple[str, str]] | None = None,
    ) -> None:
        self._bus = bus
        self._context_provider = context_provider

    def _get_context(self) -> tuple[str, str]:
        """Return (channel, chat_id) for the current request.

        Priority order:
        1. Explicit context_provider (for backwards compatibility and testing)
        2. ContextVar set by AgentLoop.handle_message (safe for concurrent tasks)
        3. Empty strings as fallback
        """
        if self._context_provider is not None:
            return self._context_provider()
        from mindclaw.orchestrator.agent_loop import (
            current_channel_var,
            current_chat_id_var,
        )
        return current_channel_var.get(), current_chat_id_var.get()

    async def execute(self, params: dict) -> str:
        text = params["message"]
        channel, chat_id = self._get_context()
        outbound = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            text=text,
        )
        await self._bus.put_outbound(outbound)
        return "Message sent to user."
