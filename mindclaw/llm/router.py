# input: litellm, config/schema.py
# output: 导出 LLMRouter, ChatResult
# pos: 大脑层核心，统一 LLM 调用接口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from dataclasses import dataclass
from typing import Any

import litellm
from litellm import acompletion
from loguru import logger

from mindclaw.config.schema import MindClawConfig

litellm.suppress_debug_info = True

_MODEL_PROVIDER_MAP = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
}


@dataclass
class ChatResult:
    content: str | None
    tool_calls: list[Any] | None


class LLMRouter:
    def __init__(self, config: MindClawConfig):
        self.config = config

    def resolve_model(self, model: str | None) -> str:
        return model or self.config.agent.default_model

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

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        resolved_model = self.resolve_model(model)
        logger.debug(f"LLM call: model={resolved_model}, messages={len(messages)}")

        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        provider = self._extract_provider(resolved_model)
        if provider and provider in self.config.providers:
            settings = self.config.providers[provider]
            if settings.api_key:
                kwargs["api_key"] = settings.api_key
            if settings.api_base:
                kwargs["api_base"] = settings.api_base

        kwargs["timeout"] = 120
        response = await acompletion(**kwargs)
        message = response.choices[0].message

        return ChatResult(
            content=message.content,
            tool_calls=message.tool_calls,
        )
