# input: mindclaw.llm
# output: LLM 路由层测试
# pos: 大脑层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_llm_router_chat_returns_text():
    """chat() 应返回 LLM 的文本回复"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.choices[0].message.tool_calls = None

    with patch("mindclaw.llm.router.acompletion", return_value=mock_response):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Hello!"
    assert result.tool_calls is None


@pytest.mark.asyncio
async def test_llm_router_chat_with_tool_calls():
    """chat() 应正确返回工具调用"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())

    mock_tool_call = AsyncMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "read_file"
    mock_tool_call.function.arguments = '{"path": "/tmp/test.txt"}'

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = None
    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    with patch("mindclaw.llm.router.acompletion", return_value=mock_response):
        result = await router.chat(
            messages=[{"role": "user", "content": "read /tmp/test.txt"}],
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )

    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].function.name == "read_file"


def test_llm_router_model_resolution():
    """应正确解析模型名称"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())
    assert router.resolve_model(None) == "claude-sonnet-4-20250514"
    assert router.resolve_model("gpt-4o") == "gpt-4o"
