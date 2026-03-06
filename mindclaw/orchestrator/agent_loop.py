# input: bus/queue.py, bus/events.py, llm/router.py, config/schema.py
# output: 导出 AgentLoop
# pos: 编排层核心，ReAct 推理循环
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import LLMRouter

SYSTEM_PROMPT = """\
You are MindClaw, a personal AI assistant. You are helpful, concise, and accurate.
Respond in the same language as the user's message.
"""


class AgentLoop:
    def __init__(
        self,
        config: MindClawConfig,
        bus: MessageBus,
        router: LLMRouter,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        # session_key -> message history
        self._sessions: dict[str, list[dict]] = {}

    def _get_history(self, session_key: str) -> list[dict]:
        if session_key not in self._sessions:
            self._sessions[session_key] = []
        return self._sessions[session_key]

    def _build_messages(self, history: list[dict], user_text: str) -> list[dict]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key
        history = self._get_history(session_key)

        messages = self._build_messages(history, inbound.text)
        logger.info(f"Agent processing: session={session_key}, user={inbound.username}")

        result = await self.router.chat(messages=messages)

        reply_text = result.content or "(no response)"

        # 保存到 session 历史
        history.append({"role": "user", "content": inbound.text})
        history.append({"role": "assistant", "content": reply_text})

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            text=reply_text,
        )
        await self.bus.put_outbound(outbound)

        logger.info(f"Agent replied: session={session_key}, len={len(reply_text)}")
