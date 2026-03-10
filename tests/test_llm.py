# input: mindclaw.llm
# output: LLM 路由层测试
# pos: 大脑层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import time
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


@pytest.mark.asyncio
async def test_llm_router_injects_provider_credentials():
    """chat() should inject api_key/api_base from config providers"""
    from mindclaw.config.schema import MindClawConfig, ProviderSettings
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig(
        providers={"anthropic": ProviderSettings(api_key="sk-test-123", api_base="https://custom.api")}
    )
    router = LLMRouter(config)

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.choices[0].message.tool_calls = None

    captured_kwargs = {}

    async def capture_acompletion(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_response

    with patch("mindclaw.llm.router.acompletion", side_effect=capture_acompletion):
        await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="anthropic/claude-sonnet-4-20250514",
        )

    assert captured_kwargs["api_key"] == "sk-test-123"
    assert captured_kwargs["api_base"] == "https://custom.api"


def test_llm_router_provider_prefix_mapping():
    """模型名不含 / 时应通过前缀映射找到 provider"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())
    assert router._extract_provider("claude-sonnet-4-20250514") == "anthropic"
    assert router._extract_provider("gpt-4o") == "openai"
    assert router._extract_provider("anthropic/claude-3") == "anthropic"
    assert router._extract_provider("unknown-model") is None


def test_llm_router_gemini_provider_mapping():
    """gemini 模型应映射到 google provider"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())
    assert router._extract_provider("gemini-2.0-flash") == "google"
    assert router._extract_provider("gemini-2.5-pro") == "google"
    assert router._extract_provider("google/gemini-2.0-flash") == "google"


def test_llm_router_deepseek_provider_mapping():
    """deepseek 模型应映射到 deepseek provider"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    router = LLMRouter(MindClawConfig())
    assert router._extract_provider("deepseek/deepseek-chat") == "deepseek"
    assert router._extract_provider("deepseek-chat") == "deepseek"


@pytest.mark.asyncio
async def test_llm_router_uses_oauth_token():
    """When provider has oauth auth_type, should route to ChatGPT backend."""
    from mindclaw.config.schema import MindClawConfig, ProviderSettings
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig(
        providers={"openai": ProviderSettings(auth_type="oauth")}
    )
    mock_oauth = AsyncMock()
    mock_oauth.get_access_token.return_value = "oauth_access_token_123"

    router = LLMRouter(config, oauth_manager=mock_oauth)

    mock_client = AsyncMock()
    mock_client.chat.return_value = ("Hello!", None)
    router._chatgpt_client = mock_client

    result = await router.chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="openai/gpt-4o",
    )

    assert result.content == "Hello!"
    mock_oauth.get_access_token.assert_awaited_once_with("openai")
    mock_client.chat.assert_awaited_once()
    call_kwargs = mock_client.chat.call_args
    assert call_kwargs.kwargs["access_token"] == "oauth_access_token_123"
    assert call_kwargs.kwargs["model"] == "openai/gpt-4o"


@pytest.mark.asyncio
async def test_llm_router_oauth_routes_to_chatgpt_backend():
    """OAuth OpenAI provider should route to ChatGPT backend, not LiteLLM."""
    from mindclaw.config.schema import MindClawConfig, ProviderSettings
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig(
        providers={"openai": ProviderSettings(auth_type="oauth")}
    )
    mock_oauth = AsyncMock()
    mock_oauth.get_access_token.return_value = "token"

    router = LLMRouter(config, oauth_manager=mock_oauth)

    mock_client = AsyncMock()
    mock_client.chat.return_value = ("Hi", None)
    router._chatgpt_client = mock_client

    result = await router.chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="openai/gpt-4o",
    )

    assert result.content == "Hi"
    # Should NOT call acompletion (LiteLLM)
    mock_client.chat.assert_awaited_once()


def test_provider_settings_auth_type_default():
    """ProviderSettings should default to api_key auth_type."""
    from mindclaw.config.schema import ProviderSettings

    settings = ProviderSettings()
    assert settings.auth_type == "api_key"


def test_provider_settings_auth_type_oauth():
    from mindclaw.config.schema import ProviderSettings

    settings = ProviderSettings(auth_type="oauth")
    assert settings.auth_type == "oauth"
