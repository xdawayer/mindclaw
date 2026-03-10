# input: mindclaw.app, mindclaw.orchestrator
# output: Phase 6 集成测试
# pos: 编排层集成测试，验证 message_user/spawn_task 在 AgentLoop 中的行为
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import patch

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.bus.queue import MessageBus
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult, LLMRouter
from mindclaw.orchestrator.agent_loop import AgentLoop
from mindclaw.orchestrator.subagent import SubAgentManager
from mindclaw.tools.message_user import MessageUserTool
from mindclaw.tools.registry import ToolRegistry
from mindclaw.tools.spawn_task import SpawnTaskTool


def _make_agent_with_tools(bus: MessageBus, config: MindClawConfig | None = None):
    """Create an AgentLoop with message_user and spawn_task tools."""
    config = config or MindClawConfig()
    config.tools.allow_dangerous_tools = True
    router = LLMRouter(config)
    registry = ToolRegistry()
    manager = SubAgentManager(config=config)

    agent = AgentLoop(
        config=config,
        bus=bus,
        router=router,
        tool_registry=registry,
    )

    msg_tool = MessageUserTool(
        bus=bus,
        context_provider=lambda: (agent._current_channel, agent._current_chat_id),
    )
    spawn_tool = SpawnTaskTool(manager=manager)
    registry.register(msg_tool)
    registry.register(spawn_tool)

    return agent


@pytest.mark.asyncio
async def test_message_user_context_from_agent_loop():
    """MessageUserTool should read context from AgentLoop via provider."""
    bus = MessageBus()
    config = MindClawConfig()
    router = LLMRouter(config)
    registry = ToolRegistry()

    agent = AgentLoop(
        config=config, bus=bus, router=router, tool_registry=registry,
    )

    msg_tool = MessageUserTool(
        bus=bus,
        context_provider=lambda: (agent._current_channel, agent._current_chat_id),
    )
    registry.register(msg_tool)

    inbound = InboundMessage(
        channel="telegram", chat_id="12345",
        user_id="wzb", username="wzb", text="hi",
    )

    mock_result = ChatResult(content="hello", tool_calls=None)
    with patch.object(router, "chat", return_value=mock_result):
        await agent.handle_message(inbound)

    # Verify the provider reads from agent's current context
    channel, chat_id = msg_tool._context_provider()
    assert channel == "telegram"
    assert chat_id == "12345"


@pytest.mark.asyncio
async def test_spawn_task_tool_registered():
    """spawn_task should be registered and callable."""
    bus = MessageBus()
    agent = _make_agent_with_tools(bus)

    tool = agent.tool_registry.get("spawn_task")
    assert tool is not None
    assert tool.name == "spawn_task"


@pytest.mark.asyncio
async def test_message_user_tool_registered():
    """message_user should be registered and callable."""
    bus = MessageBus()
    agent = _make_agent_with_tools(bus)

    tool = agent.tool_registry.get("message_user")
    assert tool is not None
    assert tool.name == "message_user"
