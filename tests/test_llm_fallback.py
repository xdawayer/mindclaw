# input: mindclaw.llm.router, mindclaw.config.schema
# output: LLM 自动降级测试
# pos: 验证主模型失败时自动切换到 fallback 模型
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import AsyncMock, patch

import pytest


def _make_mock_response(content="Hello!", tool_calls=None):
    """Create a mock LLM response."""
    resp = AsyncMock()
    resp.choices = [AsyncMock()]
    resp.choices[0].message.content = content
    resp.choices[0].message.tool_calls = tool_calls
    return resp


@pytest.mark.asyncio
async def test_fallback_on_rate_limit():
    """主模型触发 RateLimitError 时应自动降级到 fallback 模型"""
    from litellm.exceptions import RateLimitError

    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    call_count = 0

    async def mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RateLimitError(
                message="Rate limit exceeded",
                model=kwargs["model"],
                llm_provider="anthropic",
            )
        return _make_mock_response("Fallback response")

    with patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Fallback response"
    assert result.used_fallback is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_fallback_on_timeout():
    """主模型超时应自动降级到 fallback 模型"""
    import asyncio

    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    call_count = 0

    async def mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        return _make_mock_response("Timeout fallback")

    with patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Timeout fallback"
    assert result.used_fallback is True


@pytest.mark.asyncio
async def test_fallback_on_auth_error():
    """主模型认证失败应自动降级到 fallback 模型"""
    from litellm.exceptions import AuthenticationError

    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    call_count = 0

    async def mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise AuthenticationError(
                message="Invalid API key",
                model=kwargs["model"],
                llm_provider="anthropic",
            )
        return _make_mock_response("Auth fallback")

    with patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Auth fallback"
    assert result.used_fallback is True


@pytest.mark.asyncio
async def test_fallback_uses_correct_model():
    """降级时应使用 config 中配置的 fallback_model"""
    from litellm.exceptions import RateLimitError

    from mindclaw.config.schema import AgentConfig, MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig(
        agent=AgentConfig(
            default_model="claude-sonnet-4-20250514",
            fallback_model="gpt-4o-mini",
        )
    )
    router = LLMRouter(config)

    captured_models = []

    async def mock_acompletion(**kwargs):
        captured_models.append(kwargs["model"])
        if len(captured_models) == 1:
            raise RateLimitError(
                message="Rate limit",
                model=kwargs["model"],
                llm_provider="anthropic",
            )
        return _make_mock_response("OK")

    with patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion):
        await router.chat(messages=[{"role": "user", "content": "Hi"}])

    assert captured_models[0] == "claude-sonnet-4-20250514"
    assert captured_models[1] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_fallback_also_fails_raises():
    """主模型和 fallback 都失败时应抛出异常"""
    from litellm.exceptions import RateLimitError

    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    async def mock_acompletion(**kwargs):
        raise RateLimitError(
            message="Rate limit",
            model=kwargs["model"],
            llm_provider="anthropic",
        )

    with (
        patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion),
        pytest.raises(RateLimitError),
    ):
        await router.chat(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_no_fallback_when_same_model():
    """当 fallback_model 与 default_model 相同时，不应重试"""
    from litellm.exceptions import RateLimitError

    from mindclaw.config.schema import AgentConfig, MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig(
        agent=AgentConfig(
            default_model="claude-sonnet-4-20250514",
            fallback_model="claude-sonnet-4-20250514",
        )
    )
    router = LLMRouter(config)

    call_count = 0

    async def mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RateLimitError(
            message="Rate limit",
            model=kwargs["model"],
            llm_provider="anthropic",
        )

    with (
        patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion),
        pytest.raises(RateLimitError),
    ):
        await router.chat(messages=[{"role": "user", "content": "Hi"}])

    assert call_count == 1


@pytest.mark.asyncio
async def test_no_fallback_on_normal_error():
    """非限流/超时/认证错误不应触发降级，直接抛出"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    async def mock_acompletion(**kwargs):
        raise ValueError("Unexpected error")

    with (
        patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion),
        pytest.raises(ValueError, match="Unexpected error"),
    ):
        await router.chat(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_no_fallback_when_model_explicitly_specified():
    """显式指定模型时不应触发降级（用户意图明确）"""
    from litellm.exceptions import RateLimitError

    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    call_count = 0

    async def mock_acompletion(**kwargs):
        nonlocal call_count
        call_count += 1
        raise RateLimitError(
            message="Rate limit",
            model=kwargs["model"],
            llm_provider="anthropic",
        )

    with (
        patch("mindclaw.llm.router.acompletion", side_effect=mock_acompletion),
        pytest.raises(RateLimitError),
    ):
        await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="gpt-4o",
        )

    assert call_count == 1


@pytest.mark.asyncio
async def test_successful_call_no_fallback():
    """正常调用成功时 used_fallback 应为 False"""
    from mindclaw.config.schema import MindClawConfig
    from mindclaw.llm.router import LLMRouter

    config = MindClawConfig()
    router = LLMRouter(config)

    with patch(
        "mindclaw.llm.router.acompletion",
        return_value=_make_mock_response("Direct response"),
    ):
        result = await router.chat(
            messages=[{"role": "user", "content": "Hi"}],
        )

    assert result.content == "Direct response"
    assert result.used_fallback is False
