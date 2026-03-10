# input: litellm, config/schema.py, oauth/manager.py (optional), oauth/providers.py
# output: 导出 LLMRouter, ChatResult
# pos: 大脑层核心，统一 LLM 调用接口，支持 API Key 和 OAuth 认证
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import litellm
from litellm import acompletion
from litellm.exceptions import AuthenticationError, RateLimitError
from loguru import logger

from mindclaw.config.schema import MindClawConfig

if TYPE_CHECKING:
    from mindclaw.oauth.manager import OAuthManager

litellm.suppress_debug_info = True

_MODEL_PROVIDER_MAP = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "gemini": "google",
    "deepseek": "deepseek",
}

_FALLBACK_ERRORS = (RateLimitError, asyncio.TimeoutError, AuthenticationError)


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[Any] | None
    used_fallback: bool = field(default=False)


class LLMRouter:
    def __init__(
        self,
        config: MindClawConfig,
        oauth_manager: OAuthManager | None = None,
    ) -> None:
        self.config = config
        self._oauth_manager = oauth_manager

    def resolve_model(self, model: str | None) -> str:
        return model or self.config.agent.default_model

    def resolve_model_for_task(self, category: str) -> str:
        """Resolve model based on task category and routing config."""
        routing = self.config.agent.model_routing
        if routing.enabled and category in routing.categories:
            return routing.categories[category]
        return self.config.agent.default_model

    def _extract_provider(self, model: str) -> str | None:
        """Extract provider from model string.

        Prefer explicit 'provider/model' format (e.g. 'anthropic/claude-3').
        Prefix matching is a convenience fallback and may match unintended models.
        """
        if "/" in model:
            return model.split("/", 1)[0]
        for prefix, provider in _MODEL_PROVIDER_MAP.items():
            if model.startswith(prefix):
                return provider
        return None

    async def _build_kwargs(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        provider = self._extract_provider(model)
        if provider and provider in self.config.providers:
            settings = self.config.providers[provider]

            if settings.auth_type == "oauth" and self._oauth_manager is not None:
                token = await self._oauth_manager.get_access_token(provider)
                kwargs["api_key"] = token
                # Use api_base from OAuth provider config if not overridden
                from mindclaw.oauth.providers import OAUTH_PROVIDERS

                oauth_cfg = OAUTH_PROVIDERS.get(provider)
                if settings.api_base:
                    kwargs["api_base"] = settings.api_base
                elif oauth_cfg and oauth_cfg.api_base:
                    kwargs["api_base"] = oauth_cfg.api_base
            else:
                if settings.api_key:
                    kwargs["api_key"] = settings.api_key
                if settings.api_base:
                    kwargs["api_base"] = settings.api_base

        kwargs["timeout"] = 120
        return kwargs

    def _can_fallback(self, model: str, explicitly_specified: bool) -> bool:
        fallback = self.config.agent.fallback_model
        return (
            not explicitly_specified
            and fallback != model
            and bool(fallback)
        )

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        resolved_model = self.resolve_model(model)
        explicitly_specified = model is not None
        logger.debug(f"LLM call: model={resolved_model}, messages={len(messages)}")

        kwargs = await self._build_kwargs(resolved_model, messages, tools)

        try:
            response = await acompletion(**kwargs)
            message = response.choices[0].message
            return ChatResult(
                content=message.content,
                tool_calls=message.tool_calls,
                used_fallback=False,
            )
        except _FALLBACK_ERRORS as e:
            if not self._can_fallback(resolved_model, explicitly_specified):
                raise

            fallback_model = self.config.agent.fallback_model
            logger.warning(
                f"Primary model {resolved_model} failed ({type(e).__name__}), "
                f"falling back to {fallback_model}"
            )

            fallback_kwargs = await self._build_kwargs(fallback_model, messages, tools)
            response = await acompletion(**fallback_kwargs)
            message = response.choices[0].message
            return ChatResult(
                content=message.content,
                tool_calls=message.tool_calls,
                used_fallback=True,
            )
