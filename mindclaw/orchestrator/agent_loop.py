# input: bus/queue.py, bus/events.py, llm/router.py, config/schema.py, tools/registry.py
# output: 导出 AgentLoop
# pos: 编排层核心，ReAct 推理循环 (含工具调用)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import LLMRouter
from mindclaw.tools.registry import ToolRegistry

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
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        self.tool_registry = tool_registry or ToolRegistry()
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

    async def _execute_tool(self, name: str, arguments: str) -> str:
        tool = self.tool_registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            params = json.loads(arguments)
            result = await tool.execute(params)
            max_chars = self.config.tools.tool_result_max_chars
            if len(result) > max_chars:
                result = result[:max_chars] + "\n...(truncated)"
            return result
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for tool '{name}'"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key
        history = self._get_history(session_key)
        max_iterations = self.config.agent.max_iterations

        messages = self._build_messages(history, inbound.text)
        tools = self.tool_registry.to_openai_tools() or None

        logger.info(f"Agent processing: session={session_key}, user={inbound.username}")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            result = await self.router.chat(messages=messages, tools=tools)

            if not result.tool_calls:
                reply_text = result.content or "(no response)"
                break

            assistant_msg = {"role": "assistant", "content": result.content, "tool_calls": []}
            for tc in result.tool_calls:
                assistant_msg["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append(assistant_msg)

            for tc in result.tool_calls:
                logger.info(f"Tool call: {tc.function.name}")
                tool_result = await self._execute_tool(tc.function.name, tc.function.arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            reply_text = (
                f"I reached the max iterations ({max_iterations}) "
                "and couldn't complete the task."
            )

        history.append({"role": "user", "content": inbound.text})
        history.append({"role": "assistant", "content": reply_text})

        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            text=reply_text,
        )
        await self.bus.put_outbound(outbound)
        logger.info(f"Agent replied: session={session_key}, iterations={iteration}")
