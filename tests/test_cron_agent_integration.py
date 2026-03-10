# input: mindclaw.orchestrator.agent_loop, mindclaw.orchestrator.cron_context
# output: Cron 执行约束在 agent loop 中的集成测试
# pos: 验证 cron 约束（迭代限制、工具阻止、超时）在 agent loop 中的实际应用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, patch

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult, LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.tools.base import RiskLevel, Tool


class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing"
    parameters = {"type": "object", "properties": {"x": {"type": "string"}}}
    risk_level = RiskLevel.SAFE

    async def execute(self, params: dict) -> str:
        return "dummy result"


class ExecTool(Tool):
    name = "exec"
    description = "Execute shell command"
    parameters = {"type": "object", "properties": {"cmd": {"type": "string"}}}
    risk_level = RiskLevel.DANGEROUS

    async def execute(self, params: dict) -> str:
        return "executed"


def _make_cron_inbound(
    action: str = "Do something",
    max_iterations: int | None = None,
    timeout: int | None = None,
    notify_channel: str = "telegram",
    notify_chat_id: str = "12345",
) -> InboundMessage:
    metadata: dict = {
        "cron_task_id": "cron_1",
        "cron_task_name": "test-task",
    }
    if notify_channel:
        metadata["notify_channel"] = notify_channel
    if notify_chat_id:
        metadata["notify_chat_id"] = notify_chat_id
    if max_iterations is not None:
        metadata["max_iterations"] = max_iterations
    if timeout is not None:
        metadata["timeout"] = timeout
    return InboundMessage(
        channel="system",
        chat_id="cron:test-task",
        user_id="cron",
        username="CronScheduler",
        text=f"[Scheduled Task: test-task] {action}",
        metadata=metadata,
    )


def _make_agent(tmp_path) -> tuple[AgentLoop, MessageBus, LLMRouter]:
    config = MindClawConfig(knowledge={"dataDir": str(tmp_path / "data")})
    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)
    return agent, bus, router


@pytest.mark.asyncio
async def test_cron_blocks_exec_tool(tmp_path):
    """Cron execution should block exec tool (in default blocked_tools)."""
    agent, bus, router = _make_agent(tmp_path)
    agent.tool_registry.register(DummyTool())
    agent.tool_registry.register(ExecTool())

    # LLM tries to call exec, then gives up
    tc_exec = AsyncMock()
    tc_exec.id = "tc_1"
    tc_exec.function.name = "exec"
    tc_exec.function.arguments = '{"cmd": "rm -rf /"}'

    result_with_tool = ChatResult(content=None, tool_calls=[tc_exec])
    result_final = ChatResult(content="Exec was blocked", tool_calls=None)

    with patch.object(router, "chat", side_effect=[result_with_tool, result_final]):
        await agent.handle_message(_make_cron_inbound())

    outbound = await bus.get_outbound()
    assert outbound.text == "Exec was blocked"
    assert outbound.channel == "telegram"


@pytest.mark.asyncio
async def test_cron_blocks_exec_tool_returns_error():
    """Blocked cron tool should return error message."""
    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)
    agent.tool_registry.register(ExecTool())

    from mindclaw.orchestrator.cron_context import CronExecutionConstraints

    constraints = CronExecutionConstraints()
    result = await agent._execute_tool("exec", '{"cmd": "ls"}', constraints)

    assert "not allowed" in result.lower()
    assert "cron" in result.lower()


@pytest.mark.asyncio
async def test_cron_allows_safe_tools():
    """Cron execution should allow tools not in blocked_tools."""
    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)
    agent.tool_registry.register(DummyTool())

    from mindclaw.orchestrator.cron_context import CronExecutionConstraints

    constraints = CronExecutionConstraints()
    result = await agent._execute_tool("dummy", '{"x": "hello"}', constraints)

    assert result == "dummy result"


@pytest.mark.asyncio
async def test_cron_uses_custom_max_iterations(tmp_path):
    """Cron message with max_iterations in metadata should override default."""
    agent, bus, router = _make_agent(tmp_path)
    agent.config = MindClawConfig(
        agent={"maxIterations": 40},
        knowledge={"dataDir": str(tmp_path / "data")},
    )

    # LLM keeps calling tools until max_iterations is reached
    tc = AsyncMock()
    tc.id = "tc_1"
    tc.function.name = "dummy"
    tc.function.arguments = '{"x": "hi"}'

    agent.tool_registry.register(DummyTool())

    result_with_tool = ChatResult(content=None, tool_calls=[tc])

    call_count = 0

    async def mock_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 10:
            return ChatResult(content="Giving up", tool_calls=None)
        return result_with_tool

    with patch.object(router, "chat", side_effect=mock_chat):
        await agent.handle_message(_make_cron_inbound(max_iterations=5))

    # Should have been called exactly 5 times (= max_iterations from cron metadata)
    assert call_count == 5


@pytest.mark.asyncio
async def test_non_cron_uses_config_max_iterations(tmp_path):
    """Non-cron messages should use config.agent.max_iterations."""
    config = MindClawConfig(
        agent={"maxIterations": 3},
        knowledge={"dataDir": str(tmp_path / "data")},
    )
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)
    agent.tool_registry.register(DummyTool())

    tc = AsyncMock()
    tc.id = "tc_1"
    tc.function.name = "dummy"
    tc.function.arguments = '{"x": "hi"}'

    result_with_tool = ChatResult(content=None, tool_calls=[tc])

    call_count = 0

    async def mock_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 10:
            return ChatResult(content="Giving up", tool_calls=None)
        return result_with_tool

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="user1", username="user", text="hello"
    )

    with patch.object(router, "chat", side_effect=mock_chat):
        await agent.handle_message(inbound)

    outbound = await bus.get_outbound()
    assert call_count == 3
    assert "max iterations" in outbound.text.lower()


@pytest.mark.asyncio
async def test_non_cron_does_not_block_tools():
    """Non-cron messages should NOT have cron tool restrictions."""
    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)
    agent.tool_registry.register(ExecTool())

    # No cron constraints -- exec should work
    result = await agent._execute_tool("exec", '{"cmd": "ls"}')
    assert result == "executed"
