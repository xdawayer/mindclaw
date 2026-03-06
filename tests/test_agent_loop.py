# input: mindclaw.orchestrator
# output: Agent Loop 测试
# pos: 编排层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import patch

import pytest

from mindclaw.bus.events import InboundMessage
from mindclaw.config.schema import MindClawConfig
from mindclaw.llm.router import ChatResult


@pytest.mark.asyncio
async def test_agent_loop_simple_reply():
    """Agent 应处理一条消息并返回 LLM 回复"""
    from mindclaw.bus.queue import MessageBus
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="What is Python?"
    )

    mock_result = ChatResult(content="Python is a programming language.", tool_calls=None)

    with patch.object(router, "chat", return_value=mock_result):
        await agent.handle_message(inbound)

    # 验证回复被放入 outbound 队列
    outbound = await bus.get_outbound()
    assert outbound.text == "Python is a programming language."
    assert outbound.channel == "cli"
    assert outbound.chat_id == "local"


@pytest.mark.asyncio
async def test_agent_loop_builds_system_prompt():
    """Agent 应构建包含系统提示的消息列表"""
    from mindclaw.bus.queue import MessageBus
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)

    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="hi"
    )

    mock_result = ChatResult(content="hello", tool_calls=None)
    captured_messages = []

    async def capture_chat(messages, **kwargs):
        captured_messages.extend(messages)
        return mock_result

    with patch.object(router, "chat", side_effect=capture_chat):
        await agent.handle_message(inbound)

    # 第一条应该是 system message
    assert captured_messages[0]["role"] == "system"
    # 最后一条应该是 user message
    assert captured_messages[-1]["role"] == "user"
    assert captured_messages[-1]["content"] == "hi"
