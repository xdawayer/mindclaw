# input: abc, bus/queue.py, bus/events.py
# output: 导出 BaseChannel
# pos: 渠道层抽象基类，所有渠道的统一接口（含白名单 + 统一消息入口）
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from abc import ABC, abstractmethod

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus


class BaseChannel(ABC):
    def __init__(
        self,
        name: str,
        bus: MessageBus,
        allow_from: list[str] | None = None,
    ) -> None:
        self.name = name
        self.bus = bus
        self.allow_from = set(allow_from) if allow_from else None

    @abstractmethod
    async def start(self) -> None:
        """Start the channel."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel."""

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through this channel's platform."""

    def is_allowed(self, user_id: str) -> bool:
        """Check if user_id is in the whitelist. None means allow all."""
        if self.allow_from is None:
            return True
        return user_id in self.allow_from

    async def _handle_message(
        self,
        text: str,
        chat_id: str,
        user_id: str,
        username: str,
        **kwargs,
    ) -> None:
        """Unified inbound handler: whitelist check -> build InboundMessage -> enqueue."""
        if not self.is_allowed(user_id):
            return
        msg = InboundMessage(
            channel=self.name,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            text=text,
            **kwargs,
        )
        await self.bus.put_inbound(msg)
