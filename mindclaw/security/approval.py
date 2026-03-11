# input: bus/queue.py, bus/events.py, asyncio, uuid, time
# output: 导出 ApprovalManager
# pos: 安全层审批工作流，DANGEROUS 工具执行前的用户确认机制（按 session 隔离，不影响其他会话）
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import time
import uuid
from dataclasses import dataclass, field

from loguru import logger

from mindclaw.bus.events import OutboundMessage
from mindclaw.bus.queue import MessageBus

_APPROVE_WORDS = frozenset({"yes", "y", "approve"})
_REJECT_WORDS = frozenset({"no", "n", "reject"})
_ALL_REPLY_WORDS = _APPROVE_WORDS | _REJECT_WORDS


@dataclass
class ApprovalRequest:
    approval_id: str
    tool_name: str
    arguments: str
    channel: str
    chat_id: str
    created_at: float = field(default_factory=time.time)
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False


class ApprovalManager:
    """Manages user approval for DANGEROUS tool executions.

    Flow:
    1. AgentLoop calls request_approval() when a DANGEROUS tool is invoked
    2. An approval request is sent to the user via the message bus
    3. The call awaits the user's response (or timeout)
    4. The message router calls resolve() when an approval reply arrives
    """

    def __init__(self, bus: MessageBus, timeout: float = 300.0) -> None:
        self.bus = bus
        self.timeout = timeout
        self._pending: ApprovalRequest | None = None

    def has_pending(self, session_key: str | None = None) -> bool:
        """Return True if there is a pending approval.

        Args:
            session_key: When provided, only return True if the pending approval
                belongs to this session (``"<channel>:<chat_id>"``).  When
                omitted (or None), return True if *any* session has a pending
                approval.
        """
        if self._pending is None:
            return False
        if session_key is None:
            return True
        pending_key = f"{self._pending.channel}:{self._pending.chat_id}"
        return pending_key == session_key

    def is_approval_reply(self, text: str, channel: str = "", chat_id: str = "") -> bool:
        if self._pending is None:
            return False
        if channel and self._pending.channel != channel:
            return False
        if chat_id and self._pending.chat_id != chat_id:
            return False
        return text.strip().lower() in _ALL_REPLY_WORDS

    async def request_approval(
        self,
        tool_name: str,
        arguments: str,
        channel: str,
        chat_id: str,
    ) -> bool:
        approval_id = f"approval_{uuid.uuid4().hex[:8]}"
        self._pending = ApprovalRequest(
            approval_id=approval_id,
            tool_name=tool_name,
            arguments=arguments,
            channel=channel,
            chat_id=chat_id,
        )

        logger.info(f"Approval requested: {approval_id} for tool '{tool_name}'")

        await self.bus.put_outbound(OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            text=(
                f"MindClaw requests approval to execute:\n"
                f"  Tool: {tool_name}\n"
                f"  Args: {arguments}\n\n"
                f"Reply 'yes' to approve, 'no' to reject."
            ),
        ))

        try:
            await asyncio.wait_for(self._pending.event.wait(), timeout=self.timeout)
            approved = self._pending.approved
        except asyncio.TimeoutError:
            approved = False
            logger.warning(f"Approval timeout: {approval_id}")
            await self.bus.put_outbound(OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                text=f"Approval timed out after {int(self.timeout)}s. Action rejected.",
            ))
        finally:
            self._pending = None

        logger.info(f"Approval {approval_id}: {'approved' if approved else 'rejected'}")
        return approved

    def resolve(self, text: str) -> None:
        if self._pending is None:
            return
        self._pending.approved = text.strip().lower() in _APPROVE_WORDS
        self._pending.event.set()
