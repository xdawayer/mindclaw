# input: mindclaw.orchestrator.agent_loop, mindclaw.security.approval, mindclaw.bus
# output: AgentLoop 并发共享状态竞态条件测试
# pos: 验证并发 handle_message 调用中审批请求被路由到正确的 channel/chat_id
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for AgentLoop concurrent message handling.

Bug: _current_channel and _current_chat_id are instance-level variables set in
handle_message(). When 2+ messages are processed concurrently, the second write
overwrites the first, causing approval requests to be sent to the wrong channel/user.

Fix: pass channel and chat_id as parameters through the call chain:
handle_message -> _run_agent_loop -> _agent_loop_inner -> _execute_tool
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult, LLMRouter
from mindclaw.tools.base import RiskLevel, Tool
from mindclaw.tools.registry import ToolRegistry


class SlowDangerousTool(Tool):
    """A DANGEROUS tool that takes a little time to execute, giving the race a chance to occur."""

    name = "slow_exec"
    description = "Execute a slow dangerous command"
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }
    risk_level = RiskLevel.DANGEROUS

    async def execute(self, params: dict) -> str:
        await asyncio.sleep(0.01)
        return f"executed: {params.get('command', '')}"


def _make_tool_call(call_id: str, tool_name: str, args: dict) -> MagicMock:
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(args)
    return tc


@pytest.mark.asyncio
async def test_concurrent_approval_goes_to_correct_channel():
    """Reproduce the race condition bug.

    Two messages from different channels are processed concurrently.
    Message A (channel='telegram', chat_id='user_A') arrives first and triggers
    a DANGEROUS tool requiring approval.
    Message B (channel='slack', chat_id='user_B') arrives a moment later and
    OVERWRITES the shared _current_channel/_current_chat_id before A's
    _execute_tool reads them.

    With the bug: _current_channel is set to 'slack'/'user_B' by B's
    handle_message BEFORE A reads it in _execute_tool, so A's approval request
    is sent to the wrong destination.

    After the fix (channel/chat_id passed as local params), each coroutine
    carries its own values and approvals always go to the correct recipient.

    The race is made deterministic using an asyncio.Event: A's LLM call
    awaits for B to set its shared state first, then reads the (corrupted)
    shared state, proving the bug.
    """
    from mindclaw.orchestrator.agent_loop import AgentLoop
    from mindclaw.security.approval import ApprovalManager

    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(SlowDangerousTool())
    approval_manager = ApprovalManager(bus=bus, timeout=5.0)

    agent = AgentLoop(
        config=config,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_manager,
    )

    # Events used to deterministically interleave the two coroutines:
    # b_has_set_state: fires after B sets _current_channel/_current_chat_id
    # a_can_return_tool_call: fires to let A's LLM call return AFTER B has set state
    b_has_set_state = asyncio.Event()
    a_can_return_tool_call = asyncio.Event()

    # Build tool-call results
    tc_a = _make_tool_call("call_a1", "slow_exec", {"command": "cmd_A"})
    tc_b = _make_tool_call("call_b1", "slow_exec", {"command": "cmd_B"})

    a_llm_call_count = 0
    b_llm_call_count = 0

    async def dispatching_chat(messages, **kwargs):
        nonlocal a_llm_call_count, b_llm_call_count
        # Identify which message we're in by the user content
        user_text = next(
            (m["content"] for m in messages if m.get("role") == "user"), ""
        )
        if "cmd_A" in user_text:
            a_llm_call_count += 1
            if a_llm_call_count == 1:
                # Wait until B has already set _current_channel to 'slack'/'user_B'
                await b_has_set_state.wait()
                return ChatResult(content=None, tool_calls=[tc_a])
            return ChatResult(content="done_A", tool_calls=None)
        else:
            # cmd_B path
            b_llm_call_count += 1
            if b_llm_call_count == 1:
                return ChatResult(content=None, tool_calls=[tc_b])
            return ChatResult(content="done_B", tool_calls=None)

    router.chat = dispatching_chat  # type: ignore[method-assign]

    inbound_a = InboundMessage(
        channel="telegram",
        chat_id="user_A",
        user_id="uid_A",
        username="Alice",
        text="run cmd_A",
    )
    inbound_b = InboundMessage(
        channel="slack",
        chat_id="user_B",
        user_id="uid_B",
        username="Bob",
        text="run cmd_B",
    )

    # Track which channels/chat_ids received approval requests
    approval_requests: list[tuple[str, str]] = []

    async def recording_request_approval(
        tool_name: str,
        arguments: str,
        channel: str,
        chat_id: str,
    ) -> bool:
        approval_requests.append((channel, chat_id))
        return True

    approval_manager.request_approval = recording_request_approval  # type: ignore[method-assign]

    # Intercept handle_message to signal after B sets shared state.
    # We monkeypatch the instance-level set so B signals after it sets state.
    original_handle = agent.handle_message

    async def handle_b_with_signal(inbound: InboundMessage) -> None:
        """Wrap B's handle_message to signal after shared state is set."""
        # The real handle_message sets _current_channel at its start.
        # We fire b_has_set_state right after that assignment completes,
        # which in the current (buggy) code happens synchronously before
        # the first await. We simulate this by yielding control and then
        # signalling before B's LLM call completes.
        # The simplest approach: signal immediately on entry (B sets state
        # synchronously before the first await in handle_message).
        b_has_set_state.set()
        await original_handle(inbound)

    async def run_a():
        await agent.handle_message(inbound_a)

    async def run_b():
        # B starts slightly after A so A's handle_message begins first
        await asyncio.sleep(0.002)
        await handle_b_with_signal(inbound_b)

    await asyncio.gather(run_a(), run_b())

    # Both approval requests must have been sent
    assert len(approval_requests) == 2, (
        f"Expected 2 approval requests, got {len(approval_requests)}: {approval_requests}"
    )

    # CRITICAL: each approval must go to the correct channel/chat_id.
    # With the bug, A's approval was sent AFTER B set _current_channel='slack',
    # so A's approval would go to ('slack', 'user_B') instead of ('telegram', 'user_A').
    channels_seen = {(ch, cid) for ch, cid in approval_requests}
    assert ("telegram", "user_A") in channels_seen, (
        f"Approval for user_A was not sent to telegram/user_A. "
        f"Got: {approval_requests}"
    )
    assert ("slack", "user_B") in channels_seen, (
        f"Approval for user_B was not sent to slack/user_B. "
        f"Got: {approval_requests}"
    )


@pytest.mark.asyncio
async def test_no_shared_state_attributes_after_fix():
    """After the fix, AgentLoop must NOT have _current_channel/_current_chat_id attributes."""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)

    assert not hasattr(agent, "_current_channel"), (
        "_current_channel must be removed from AgentLoop instance state after fix"
    )
    assert not hasattr(agent, "_current_chat_id"), (
        "_current_chat_id must be removed from AgentLoop instance state after fix"
    )


@pytest.mark.asyncio
async def test_execute_tool_accepts_channel_and_chat_id_params():
    """After the fix, _execute_tool must accept channel and chat_id parameters."""
    import inspect

    from mindclaw.orchestrator.agent_loop import AgentLoop

    sig = inspect.signature(AgentLoop._execute_tool)
    param_names = list(sig.parameters.keys())

    assert "channel" in param_names, (
        "_execute_tool must have a 'channel' parameter after fix"
    )
    assert "chat_id" in param_names, (
        "_execute_tool must have a 'chat_id' parameter after fix"
    )
