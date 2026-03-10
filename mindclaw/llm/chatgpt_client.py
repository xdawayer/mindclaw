# input: httpx, oauth/token_store, json, base64
# output: 导出 ChatGPTBackendClient
# pos: ChatGPT 后端直连客户端，使用 Responses API 格式，走订阅配额
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

_CHATGPT_BACKEND_URL = "https://chatgpt.com/backend-api/codex/responses"


@dataclass
class _FunctionInfo:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    """Mimics LiteLLM's tool_call object interface for AgentLoop compatibility."""

    id: str
    function: _FunctionInfo


def _extract_account_id(access_token: str) -> str:
    """Extract chatgpt_account_id from JWT access_token claims."""
    parts = access_token.split(".")
    if len(parts) < 2:
        return ""
    payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("https://api.openai.com/auth", {}).get(
            "chatgpt_account_id", ""
        )
    except Exception:
        logger.warning("Failed to decode JWT for account_id")
        return ""


def _strip_provider_prefix(model: str) -> str:
    """Remove 'openai/' prefix from model name."""
    if model.startswith("openai/"):
        return model[7:]
    return model


def _convert_tools(tools: list[dict] | None) -> list[dict] | None:
    """Convert Chat Completions tool format to Responses API format.

    Chat Completions: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    Responses API:    {"type": "function", "name": ..., "description": ..., "parameters": ...}
    """
    if not tools:
        return None
    result = []
    for tool in tools:
        if tool.get("type") == "function" and "function" in tool:
            fn = tool["function"]
            result.append({
                "type": "function",
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
        else:
            result.append(tool)
    return result or None


def _convert_messages_to_input(
    messages: list[dict],
) -> tuple[str, list[dict]]:
    """Convert Chat Completions messages to Responses API instructions + input.

    Returns:
        (instructions, input_items) tuple.
    """
    instructions = ""
    input_items: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")

        if role == "system":
            instructions = content or ""

        elif role == "user":
            input_items.append({
                "type": "message",
                "role": "user",
                "content": content or "",
            })

        elif role == "assistant":
            # Add text content as message if present
            if content:
                input_items.append({
                    "type": "message",
                    "role": "assistant",
                    "content": content,
                })

            # Convert tool_calls to function_call items
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                input_items.append({
                    "type": "function_call",
                    "call_id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                })

        elif role == "tool":
            input_items.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id", ""),
                "output": content or "",
            })

    return instructions, input_items


def _parse_sse_response(
    text: str,
) -> tuple[str | None, list[_ToolCall] | None]:
    """Parse SSE response text into content and tool_calls."""
    content_parts: list[str] = []
    # call_id -> (name, arguments_parts)
    function_calls: dict[str, tuple[str, list[str]]] = {}
    current_call_id: str | None = None

    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break

        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "response.output_text.delta":
            content_parts.append(event.get("delta", ""))

        elif event_type == "response.output_item.added":
            item = event.get("item", {})
            if item.get("type") == "function_call":
                call_id = item.get("call_id", "")
                name = item.get("name", "")
                function_calls[call_id] = (name, [])
                current_call_id = call_id

        elif event_type == "response.function_call_arguments.delta":
            delta = event.get("delta", "")
            if current_call_id and current_call_id in function_calls:
                function_calls[current_call_id][1].append(delta)

        elif event_type == "response.output_item.done":
            item = event.get("item", {})
            if item.get("type") == "function_call":
                # Use the final complete item data
                call_id = item.get("call_id", "")
                name = item.get("name", "")
                arguments = item.get("arguments", "{}")
                function_calls[call_id] = (name, [arguments])
                current_call_id = None

    content = "".join(content_parts) if content_parts else None
    tool_calls: list[_ToolCall] | None = None

    if function_calls:
        tool_calls = []
        for call_id, (name, arg_parts) in function_calls.items():
            tool_calls.append(_ToolCall(
                id=call_id,
                function=_FunctionInfo(
                    name=name,
                    arguments="".join(arg_parts),
                ),
            ))

    return content, tool_calls


class ChatGPTBackendClient:
    """Direct client for ChatGPT backend Responses API (subscription quota)."""

    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        access_token: str,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[str | None, list[_ToolCall] | None]:
        """Call ChatGPT backend Responses API.

        Args:
            access_token: Raw OAuth access_token (JWT).
            model: Model name (with or without 'openai/' prefix).
            messages: Chat Completions format messages.
            tools: Chat Completions format tools.

        Returns:
            (content, tool_calls) tuple compatible with ChatResult.
        """
        model = _strip_provider_prefix(model)
        account_id = _extract_account_id(access_token)
        instructions, input_items = _convert_messages_to_input(messages)
        converted_tools = _convert_tools(tools)

        body: dict[str, Any] = {
            "model": model,
            "instructions": instructions or "You are a helpful assistant.",
            "input": input_items,
            "store": False,
            "stream": True,
        }
        if converted_tools:
            body["tools"] = converted_tools

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id

        logger.debug(
            f"ChatGPT backend call: model={model}, "
            f"input_items={len(input_items)}, "
            f"tools={len(converted_tools) if converted_tools else 0}"
        )

        client = self._get_client()
        response = await client.post(
            _CHATGPT_BACKEND_URL,
            headers=headers,
            json=body,
        )

        if response.status_code != 200:
            error_text = response.text[:200]
            logger.error(
                f"ChatGPT backend error: status={response.status_code}, "
                f"body={error_text}"
            )
            raise RuntimeError(
                f"ChatGPT backend returned {response.status_code}: {error_text}"
            )

        return _parse_sse_response(response.text)
