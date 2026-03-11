# input: litellm, config/schema.py, oauth/manager.py (optional), oauth/providers.py,
#        llm/chatgpt_client.py
# output: 导出 LLMRouter, ChatResult
# pos: 大脑层核心，统一 LLM 调用接口，支持 API Key / OAuth(ChatGPT 后端) / LiteLLM
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import litellm
from litellm import acompletion
from litellm.exceptions import AuthenticationError, BadRequestError, RateLimitError
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

_FALLBACK_ERRORS = (
    RateLimitError, asyncio.TimeoutError, AuthenticationError, RuntimeError,
    BadRequestError,
)

_DEEPSEEK_REASONER_MODELS = frozenset({"deepseek/deepseek-reasoner", "deepseek-reasoner"})


def _sanitize_messages_for_model(model: str, messages: list[dict]) -> list[dict]:
    """Clean message history for cross-model compatibility.

    DeepSeek Reasoner requires ``reasoning_content`` on assistant messages;
    other models choke on that field.  This function adds or strips the field
    as needed so the history can be sent to *any* provider.
    """
    is_reasoner = model in _DEEPSEEK_REASONER_MODELS
    cleaned: list[dict] = []
    for msg in messages:
        if msg.get("role") != "assistant":
            cleaned.append(msg)
            continue
        copy = dict(msg)
        if is_reasoner:
            # Reasoner requires the field on every assistant message
            if "reasoning_content" not in copy or copy["reasoning_content"] is None:
                copy["reasoning_content"] = ""
        else:
            # Other models reject the unknown field
            copy.pop("reasoning_content", None)
        cleaned.append(copy)
    return cleaned


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[Any] | None
    used_fallback: bool = field(default=False)
    reasoning_content: str | None = field(default=None)


class LLMRouter:
    def __init__(
        self,
        config: MindClawConfig,
        oauth_manager: OAuthManager | None = None,
    ) -> None:
        self.config = config
        self._oauth_manager = oauth_manager
        self._chatgpt_client: Any = None

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

    def _is_chatgpt_backend(self, model: str) -> bool:
        """Check if this model should use the ChatGPT backend (OAuth subscription)."""
        provider = self._extract_provider(model)
        if provider != "openai" or self._oauth_manager is None:
            return False
        settings = self.config.providers.get("openai")
        return settings is not None and settings.auth_type == "oauth"

    def _get_chatgpt_client(self) -> Any:
        if self._chatgpt_client is None:
            from mindclaw.llm.chatgpt_client import ChatGPTBackendClient

            self._chatgpt_client = ChatGPTBackendClient(timeout=120)
        return self._chatgpt_client

    async def _chat_chatgpt_backend(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> ChatResult:
        """Call via ChatGPT backend Responses API (subscription quota)."""
        if self._oauth_manager is None:
            raise RuntimeError("OAuth manager required for ChatGPT backend")
        access_token = await self._oauth_manager.get_access_token("openai")
        client = self._get_chatgpt_client()
        cleaned = _sanitize_messages_for_model(model, messages)
        content, tool_calls = await client.chat(
            access_token=access_token,
            model=model,
            messages=cleaned,
            tools=tools,
        )
        return ChatResult(
            content=content,
            tool_calls=tool_calls,
            used_fallback=False,
        )

    async def _build_kwargs(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> dict[str, Any]:
        cleaned = _sanitize_messages_for_model(model, messages)
        kwargs: dict[str, Any] = {"model": model, "messages": cleaned}
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

    def _can_fallback(self, model: str) -> bool:
        fallback = self.config.agent.fallback_model
        return fallback != model and bool(fallback)

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        resolved_model = self.resolve_model(model)
        logger.debug(f"LLM call: model={resolved_model}, messages={len(messages)}")

        try:
            # Route OpenAI OAuth models to ChatGPT backend
            if self._is_chatgpt_backend(resolved_model):
                return await self._chat_chatgpt_backend(
                    resolved_model, messages, tools
                )

            # All other models go through LiteLLM
            kwargs = await self._build_kwargs(resolved_model, messages, tools)
            response = await acompletion(**kwargs)
            message = response.choices[0].message
            return ChatResult(
                content=message.content,
                tool_calls=message.tool_calls,
                used_fallback=False,
                reasoning_content=getattr(message, "reasoning_content", None),
            )
        except _FALLBACK_ERRORS as e:
            if not self._can_fallback(resolved_model):
                raise

            fallback_model = self.config.agent.fallback_model
            logger.warning(
                f"Primary model {resolved_model} failed ({type(e).__name__}), "
                f"falling back to {fallback_model}"
            )

            # Fallback always goes through LiteLLM (non-OAuth fallback model)
            fallback_kwargs = await self._build_kwargs(fallback_model, messages, tools)
            response = await acompletion(**fallback_kwargs)
            message = response.choices[0].message
            return ChatResult(
                content=message.content,
                tool_calls=message.tool_calls,
                used_fallback=True,
                reasoning_content=getattr(message, "reasoning_content", None),
            )
