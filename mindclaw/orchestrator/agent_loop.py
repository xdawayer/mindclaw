# input: bus/queue.py, bus/events.py, llm/router.py, config/schema.py,
#        tools/registry.py, security/approval.py, knowledge/session.py,
#        knowledge/memory.py, orchestrator/context.py, orchestrator/cron_context.py,
#        plugins/hooks.py
# output: 导出 AgentLoop
# pos: 编排层核心，ReAct 推理循环 (含工具调用 + cron 执行约束 + before_tool/after_tool hooks)
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import asyncio
import json
from pathlib import Path

from loguru import logger

from mindclaw.bus.events import InboundMessage, OutboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.knowledge.memory import MemoryManager
from mindclaw.knowledge.session import SessionStore
from mindclaw.llm.router import LLMRouter
from mindclaw.orchestrator.context import ContextBuilder
from mindclaw.orchestrator.cron_context import (
    CronExecutionConstraints,
    parse_cron_constraints_if_cron,
)
from mindclaw.plugins.hooks import HookRegistry
from mindclaw.security.approval import ApprovalManager
from mindclaw.tools.base import RiskLevel
from mindclaw.tools.registry import ToolRegistry

MAX_HISTORY_MESSAGES = 100


class AgentLoop:
    def __init__(
        self,
        config: MindClawConfig,
        bus: MessageBus,
        router: LLMRouter,
        tool_registry: ToolRegistry | None = None,
        approval_manager: ApprovalManager | None = None,
        session_store: SessionStore | None = None,
        memory_manager: MemoryManager | None = None,
        context_builder: ContextBuilder | None = None,
        hook_registry: HookRegistry | None = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.router = router
        self.tool_registry = tool_registry or ToolRegistry()
        self.approval_manager = approval_manager
        self.hook_registry = hook_registry or HookRegistry()

        data_dir = Path(config.knowledge.data_dir)
        self.session_store = session_store or SessionStore(data_dir=data_dir)
        self.memory_manager = memory_manager or MemoryManager(
            data_dir=data_dir, router=router, config=config,
        )
        self.context_builder = context_builder or ContextBuilder(
            memory_manager=self.memory_manager,
        )

        self._current_channel: str = ""
        self._current_chat_id: str = ""

    def _get_history(self, session_key: str) -> list[dict]:
        history, _ = self.session_store.load(session_key)
        if len(history) > MAX_HISTORY_MESSAGES:
            cutoff = max(0, len(history) - MAX_HISTORY_MESSAGES)
            while cutoff > 0 and history[cutoff].get("role") != "user":
                cutoff -= 1
            history = history[cutoff:]
        return self._sanitize_history(history)

    @staticmethod
    def _sanitize_history(history: list[dict]) -> list[dict]:
        """Remove orphaned tool messages that lack a preceding tool_calls assistant message."""
        result: list[dict] = []
        pending_tool_call_ids: set[str] = set()
        for msg in history:
            role = msg.get("role")
            if role == "assistant" and msg.get("tool_calls"):
                pending_tool_call_ids = {
                    tc.get("id", "") for tc in msg["tool_calls"] if isinstance(tc, dict)
                }
                result.append(msg)
            elif role == "tool":
                tc_id = msg.get("tool_call_id", "")
                if tc_id in pending_tool_call_ids:
                    result.append(msg)
                    pending_tool_call_ids.discard(tc_id)
                # else: orphaned tool message, skip it
            else:
                pending_tool_call_ids = set()
                result.append(msg)
        return result

    async def _build_messages(
        self,
        history: list[dict],
        user_text: str,
        cron_constraints: CronExecutionConstraints | None = None,
    ) -> list[dict]:
        if cron_constraints is not None:
            system_prompt = self.context_builder.build_cron_system_prompt(
                cron_constraints
            )
        else:
            system_prompt = await self.context_builder.abuild_system_prompt(
                user_message=user_text
            )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})
        return messages

    async def _run_agent_loop(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_iterations: int,
        routed_model: str,
        cron_constraints: CronExecutionConstraints | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """Core ReAct loop, optionally wrapped with asyncio timeout."""
        coro = self._agent_loop_inner(
            messages, tools, max_iterations, routed_model, cron_constraints,
        )
        if timeout_seconds is not None:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        return await coro

    async def _agent_loop_inner(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_iterations: int,
        routed_model: str,
        cron_constraints: CronExecutionConstraints | None = None,
    ) -> str:
        """Inner ReAct loop (tool calls + LLM turns)."""
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            result = await self.router.chat(
                messages=messages, tools=tools, model=routed_model,
            )

            if not result.tool_calls:
                return result.content or "(no response)"

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
                tool_result = await self._execute_tool(
                    tc.function.name, tc.function.arguments, cron_constraints,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        return (
            f"I reached the max iterations ({max_iterations}) "
            "and couldn't complete the task."
        )

    async def _execute_tool(
        self,
        name: str,
        arguments: str,
        cron_constraints: CronExecutionConstraints | None = None,
    ) -> str:
        tool = self.tool_registry.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        # Cron constraint: block restricted tools
        if cron_constraints and cron_constraints.is_tool_blocked(name):
            logger.warning(f"Cron constraints blocked tool '{name}'")
            return f"Error: tool '{name}' is not allowed in cron execution"
        if tool.risk_level == RiskLevel.DANGEROUS:
            if not self.config.tools.allow_dangerous_tools:
                logger.warning(f"Blocked DANGEROUS tool '{name}' - not enabled")
                return f"Error: tool '{name}' requires allowDangerousTools in config"
            if self.approval_manager is not None:
                approved = await self.approval_manager.request_approval(
                    tool_name=name,
                    arguments=arguments,
                    channel=self._current_channel,
                    chat_id=self._current_chat_id,
                )
                if not approved:
                    logger.warning(f"DANGEROUS tool '{name}' was not approved")
                    return f"Error: tool '{name}' execution was not approved"
            else:
                logger.warning(
                    f"Executing DANGEROUS tool '{name}' without approval manager"
                )
        try:
            params = json.loads(arguments)

            # before_tool hook: allows parameter modification
            if self.hook_registry.has_handlers("before_tool"):
                hook_result = await self.hook_registry.call_with_result(
                    "before_tool", tool_name=name, params=params
                )
                params = hook_result.get("params", params)

            result = await tool.execute(params)
            max_chars = (
                tool.max_result_chars
                if tool.max_result_chars is not None
                else self.config.tools.tool_result_max_chars
            )
            if len(result) > max_chars:
                result = result[:max_chars] + "\n...(truncated)"

            # after_tool hook: notification only
            await self.hook_registry.call(
                "after_tool", tool_name=name, params=params, result=result
            )

            return result
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for tool '{name}'"
        except Exception as e:
            return f"Error executing tool '{name}': {e}"

    async def handle_message(self, inbound: InboundMessage) -> None:
        session_key = inbound.session_key

        # Cron notification routing: only honor metadata from trusted cron source
        is_cron = inbound.channel == "system" and inbound.user_id == "cron"
        notify_channel = ""
        notify_chat_id = ""
        if is_cron:
            notify_channel = inbound.metadata.get("notify_channel", "")
            notify_chat_id = inbound.metadata.get("notify_chat_id", "")

        if notify_channel:
            self._current_channel = notify_channel
            self._current_chat_id = notify_chat_id
        else:
            self._current_channel = inbound.channel
            self._current_chat_id = inbound.chat_id

        # Parse cron execution constraints (returns None for non-cron messages)
        cron_constraints = parse_cron_constraints_if_cron(
            channel=inbound.channel,
            user_id=inbound.user_id,
            metadata=inbound.metadata,
        )

        history = self._get_history(session_key)
        initial_history_len = len(history)
        max_iterations = (
            cron_constraints.max_iterations
            if cron_constraints
            else max(1, self.config.agent.max_iterations)
        )

        messages = await self._build_messages(
            history, inbound.text, cron_constraints=cron_constraints,
        )
        tools = self.tool_registry.to_openai_tools() or None

        # Model routing: classify user intent and select appropriate model
        from mindclaw.llm.classifier import classify_intent

        category = classify_intent(inbound.text)
        routed_model = self.router.resolve_model_for_task(category)
        logger.info(
            f"Agent processing: session={session_key}, user={inbound.username}, "
            f"category={category}, model={routed_model}"
        )

        try:
            reply_text = await self._run_agent_loop(
                messages=messages,
                tools=tools,
                max_iterations=max_iterations,
                routed_model=routed_model,
                cron_constraints=cron_constraints,
                timeout_seconds=(
                    cron_constraints.timeout_seconds if cron_constraints else None
                ),
            )
        except asyncio.TimeoutError:
            # Do not persist partial state from timed-out execution
            logger.warning(f"Cron task timed out: session={session_key}")
            out_channel = notify_channel or inbound.channel
            out_chat_id = notify_chat_id or inbound.chat_id
            if out_channel != "system":
                await self.bus.put_outbound(OutboundMessage(
                    channel=out_channel, chat_id=out_chat_id, text="Cron task timed out.",
                ))
            return
        except Exception:
            # Session poisoning protection: new messages are NOT persisted
            # because append() only runs after successful completion
            raise

        # Persist new messages to SessionStore
        new_messages = list(messages[1 + initial_history_len:])
        new_messages.append({"role": "assistant", "content": reply_text})
        self.session_store.append(session_key, new_messages)

        # Check for automatic consolidation
        unconsolidated, _ = self.session_store.load(session_key)
        if self.memory_manager.should_consolidate(len(unconsolidated)):
            try:
                await self.memory_manager.consolidate(session_key, self.session_store)
            except Exception:
                logger.exception("Auto-consolidation failed")

        # Route outbound to notify channel if set, otherwise to inbound channel
        out_channel = notify_channel or inbound.channel
        out_chat_id = notify_chat_id or inbound.chat_id

        # Skip putting outbound if destination is "system" (no registered channel)
        if out_channel == "system":
            logger.warning(
                f"Cron task output has no notify_channel, skipping outbound: "
                f"session={session_key}"
            )
        else:
            outbound = OutboundMessage(
                channel=out_channel,
                chat_id=out_chat_id,
                text=reply_text,
            )
            await self.bus.put_outbound(outbound)

        logger.info(f"Agent replied: session={session_key}")
