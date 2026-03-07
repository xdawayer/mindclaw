# input: mindclaw.orchestrator, mindclaw.tools, mindclaw.security.approval
# output: Agent Loop 工具集成测试
# pos: 编排层工具调用集成测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
from unittest.mock import MagicMock, patch

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult, LLMRouter
from mindclaw.tools.base import RiskLevel, Tool
from mindclaw.tools.registry import ToolRegistry


class FakeReadTool(Tool):
    name = "read_file"
    description = "Read a file"
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }
    risk_level = RiskLevel.SAFE

    async def execute(self, params: dict) -> str:
        return "file content: hello world"


class FakeDangerousTool(Tool):
    name = "exec"
    description = "Execute command"
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }
    risk_level = RiskLevel.DANGEROUS

    async def execute(self, params: dict) -> str:
        return "executed"


@pytest.mark.asyncio
async def test_agent_loop_with_tool_call():
    """Agent 应执行工具调用并将结果返回 LLM"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeReadTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="read test.txt"
    )

    # First LLM call: return tool call
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = json.dumps({"path": "test.txt"})

    call_1 = ChatResult(content=None, tool_calls=[mock_tool_call])
    # Second LLM call: return final reply
    call_2 = ChatResult(content="The file contains: hello world", tool_calls=None)

    call_count = 0

    async def mock_chat(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return call_1
        return call_2

    with patch.object(router, "chat", side_effect=mock_chat):
        await agent.handle_message(inbound)

    outbound = await bus.get_outbound()
    assert "hello world" in outbound.text
    assert call_count == 2


@pytest.mark.asyncio
async def test_agent_loop_max_iterations():
    """Agent 应在达到最大迭代次数后停止"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig(agent={"maxIterations": 3})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeReadTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="loop forever"
    )

    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_1"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = json.dumps({"path": "test.txt"})

    infinite_call = ChatResult(content=None, tool_calls=[mock_tool_call])

    with patch.object(router, "chat", return_value=infinite_call):
        await agent.handle_message(inbound)

    outbound = await bus.get_outbound()
    assert "max iterations" in outbound.text.lower() or "iteration" in outbound.text.lower()


@pytest.mark.asyncio
async def test_agent_loop_blocks_dangerous_tools():
    """DANGEROUS 工具在未启用时应被拒绝"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()  # allow_dangerous_tools defaults to False
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    result = await agent._execute_tool("exec", '{"command": "ls"}')
    assert "requires" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_agent_loop_allows_dangerous_when_enabled():
    """DANGEROUS 工具在启用后应正常执行"""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())

    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)

    result = await agent._execute_tool("exec", '{"command": "ls"}')
    assert result == "executed"


@pytest.mark.asyncio
async def test_dangerous_tool_triggers_approval_and_approved():
    """DANGEROUS tool with approval_manager: approved -> execute."""
    import asyncio

    from mindclaw.orchestrator.agent_loop import AgentLoop
    from mindclaw.security.approval import ApprovalManager

    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())
    approval_manager = ApprovalManager(bus=bus, timeout=5.0)

    agent = AgentLoop(
        config=config,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_manager,
    )
    # Set context (normally set by handle_message)
    agent._current_channel = "cli"
    agent._current_chat_id = "local"

    async def grant():
        await asyncio.sleep(0.05)
        await bus.get_outbound()  # approval request message
        approval_manager.resolve("yes")

    asyncio.create_task(grant())
    result = await agent._execute_tool("exec", '{"command": "ls"}')
    assert result == "executed"


@pytest.mark.asyncio
async def test_dangerous_tool_triggers_approval_and_rejected():
    """DANGEROUS tool with approval_manager: rejected -> error."""
    import asyncio

    from mindclaw.orchestrator.agent_loop import AgentLoop
    from mindclaw.security.approval import ApprovalManager

    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())
    approval_manager = ApprovalManager(bus=bus, timeout=5.0)

    agent = AgentLoop(
        config=config,
        bus=bus,
        router=router,
        tool_registry=registry,
        approval_manager=approval_manager,
    )
    agent._current_channel = "cli"
    agent._current_chat_id = "local"

    async def reject():
        await asyncio.sleep(0.05)
        await bus.get_outbound()
        approval_manager.resolve("no")

    asyncio.create_task(reject())
    result = await agent._execute_tool("exec", '{"command": "ls"}')
    assert "not approved" in result.lower() or "rejected" in result.lower()


@pytest.mark.asyncio
async def test_dangerous_tool_no_approval_manager_still_works():
    """DANGEROUS tool without approval_manager: backward compatible."""
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig(tools={"allowDangerousTools": True})
    bus = MessageBus()
    router = LLMRouter(config)
    registry = ToolRegistry()
    registry.register(FakeDangerousTool())

    # No approval_manager passed
    agent = AgentLoop(config=config, bus=bus, router=router, tool_registry=registry)
    result = await agent._execute_tool("exec", '{"command": "ls"}')
    assert result == "executed"
