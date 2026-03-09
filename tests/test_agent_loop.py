# input: mindclaw.orchestrator, mindclaw.knowledge
# output: Agent Loop 测试 (含 SessionStore/ContextBuilder 集成)
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


@pytest.mark.asyncio
async def test_session_history_rolls_back_on_error():
    """Error during processing should not pollute session history."""
    from mindclaw.bus.queue import MessageBus
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local",
        user_id="wzb", username="wzb", text="trigger error",
    )

    async def exploding_chat(messages, **kwargs):
        raise RuntimeError("LLM exploded")

    with patch.object(router, "chat", side_effect=exploding_chat):
        with pytest.raises(RuntimeError, match="LLM exploded"):
            await agent.handle_message(inbound)

    # Session history should be empty (rolled back)
    history = agent._get_history("cli:local")
    assert len(history) == 0


@pytest.mark.asyncio
async def test_session_history_preserved_on_success():
    """Successful processing should persist to history."""
    from mindclaw.bus.queue import MessageBus
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local",
        user_id="wzb", username="wzb", text="hello",
    )

    mock_result = ChatResult(content="Hi there!", tool_calls=None)
    with patch.object(router, "chat", return_value=mock_result):
        await agent.handle_message(inbound)

    await bus.get_outbound()
    history = agent._get_history("cli:local")
    # Should have: user message + assistant reply
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_agent_persists_session_to_store():
    """AgentLoop should persist messages via SessionStore."""
    import tempfile
    from pathlib import Path

    from mindclaw.bus.queue import MessageBus
    from mindclaw.knowledge.session import SessionStore
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    with tempfile.TemporaryDirectory() as tmp:
        config = MindClawConfig()
        bus = MessageBus()
        router = LLMRouter(config)
        store = SessionStore(data_dir=Path(tmp))
        agent = AgentLoop(config=config, bus=bus, router=router, session_store=store)

        inbound = InboundMessage(
            channel="cli", chat_id="local", user_id="wzb", username="wzb", text="hi"
        )
        mock_result = ChatResult(content="hello back", tool_calls=None)
        with patch.object(router, "chat", return_value=mock_result):
            await agent.handle_message(inbound)

        loaded, total = store.load("cli:local")
        assert total >= 2  # at least user msg + assistant reply


@pytest.mark.asyncio
async def test_agent_uses_context_builder():
    """AgentLoop should use ContextBuilder for system prompt (contains date)."""
    from mindclaw.bus.queue import MessageBus
    from mindclaw.llm.router import LLMRouter
    from mindclaw.orchestrator.agent_loop import AgentLoop

    config = MindClawConfig()
    bus = MessageBus()
    router = LLMRouter(config)
    agent = AgentLoop(config=config, bus=bus, router=router)

    inbound = InboundMessage(
        channel="cli", chat_id="local", user_id="wzb", username="wzb", text="test"
    )
    mock_result = ChatResult(content="reply", tool_calls=None)
    captured = []

    async def capture_chat(messages, **kwargs):
        captured.extend(messages)
        return mock_result

    with patch.object(router, "chat", side_effect=capture_chat):
        await agent.handle_message(inbound)

    system_msg = captured[0]
    assert system_msg["role"] == "system"
    assert "Current Date" in system_msg["content"]
