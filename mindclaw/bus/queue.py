# input: asyncio, bus/events.py
# output: 导出 MessageBus
# pos: 消息总线核心，解耦渠道与 Agent，含去重和限流
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import time

from .events import InboundMessage, OutboundMessage

_DEFAULT_DEDUP_WINDOW = 5.0
_DEFAULT_RATE_LIMIT = 30
_DEFAULT_RATE_WINDOW = 60.0


class MessageBus:
    def __init__(
        self,
        dedup_window: float = _DEFAULT_DEDUP_WINDOW,
        rate_limit: int = _DEFAULT_RATE_LIMIT,
        rate_window: float = _DEFAULT_RATE_WINDOW,
    ) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

        self._dedup_window = dedup_window
        self._dedup_cache: dict[str, float] = {}

        self._rate_limit = rate_limit
        self._rate_window = rate_window
        self._rate_log: dict[str, list[float]] = {}

    # ── Original methods (unchanged) ──

    async def put_inbound(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    async def get_inbound(self) -> InboundMessage:
        return await self.inbound.get()

    async def put_outbound(self, msg: OutboundMessage) -> None:
        await self.outbound.put(msg)

    async def get_outbound(self) -> OutboundMessage:
        return await self.outbound.get()

    # ── Dedup ──

    def _dedup_key(self, msg: InboundMessage) -> str:
        return f"{msg.channel}:{msg.chat_id}:{msg.text}"

    def _clean_dedup_cache(self, now: float) -> None:
        self._dedup_cache = {
            k: ts for k, ts in self._dedup_cache.items()
            if now - ts <= self._dedup_window
        }

    async def put_inbound_dedup(self, msg: InboundMessage) -> bool:
        """Put inbound message with dedup. Returns True if accepted, False if duplicate."""
        now = time.monotonic()
        self._clean_dedup_cache(now)
        key = self._dedup_key(msg)
        if key in self._dedup_cache:
            return False
        self._dedup_cache[key] = now
        await self.inbound.put(msg)
        return True

    # ── Rate limiting ──

    def _clean_rate_log(self, session_key: str, now: float) -> None:
        if session_key not in self._rate_log:
            return
        cutoff = now - self._rate_window
        self._rate_log = {
            k: [ts for ts in timestamps if ts > cutoff]
            for k, timestamps in self._rate_log.items()
            if k == session_key or any(ts > cutoff for ts in timestamps)
        }

    async def put_inbound_rated(self, msg: InboundMessage) -> bool:
        """Put inbound message with rate limiting. Returns True if accepted."""
        now = time.monotonic()
        session_key = msg.session_key
        self._clean_rate_log(session_key, now)
        timestamps = self._rate_log.get(session_key, [])
        if len(timestamps) >= self._rate_limit:
            return False
        self._rate_log = {
            **self._rate_log,
            session_key: [*timestamps, now],
        }
        await self.inbound.put(msg)
        return True
