# input: plugins/manifest.py (VALID_HOOK_NAMES), loguru
# output: 导出 HookRegistry
# pos: Hook 注册表与事件分发器，管理插件 hook 的注册和调用
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from mindclaw.plugins.manifest import VALID_HOOK_NAMES

HookHandler = Callable[..., Coroutine[Any, Any, dict | None]]


@dataclass(frozen=True)
class _HookEntry:
    plugin_name: str
    handler: HookHandler


class HookRegistry:
    """Registry for plugin hook handlers with sequential dispatch."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[_HookEntry]] = {}

    def register(self, event: str, plugin_name: str, handler: HookHandler) -> None:
        """Register a hook handler for an event."""
        if event not in VALID_HOOK_NAMES:
            raise ValueError(
                f"Invalid hook event: '{event}'. Valid: {sorted(VALID_HOOK_NAMES)}"
            )
        entries = self._hooks.setdefault(event, [])
        entries.append(_HookEntry(plugin_name=plugin_name, handler=handler))

    def has_handlers(self, event: str) -> bool:
        """Check if any handlers are registered for an event."""
        return bool(self._hooks.get(event))

    def unregister_plugin(self, plugin_name: str) -> None:
        """Remove all handlers registered by a plugin."""
        for event in list(self._hooks):
            self._hooks[event] = [
                e for e in self._hooks[event] if e.plugin_name != plugin_name
            ]
            if not self._hooks[event]:
                del self._hooks[event]

    async def call(self, event: str, **kwargs: Any) -> None:
        """Call all handlers for an event sequentially. Errors are logged, not raised."""
        for entry in self._hooks.get(event, []):
            try:
                await entry.handler(**kwargs)
            except Exception:
                logger.exception(
                    f"Hook handler error: plugin={entry.plugin_name}, event={event}"
                )

    async def call_with_result(self, event: str, **kwargs: Any) -> dict:
        """Call handlers sequentially, chaining returned dicts into kwargs.

        Each handler may return a dict to update kwargs for the next handler.
        If a handler returns None, kwargs pass through unchanged.
        """
        current = dict(kwargs)
        for entry in self._hooks.get(event, []):
            try:
                result = await entry.handler(**current)
                if result is not None and isinstance(result, dict):
                    current.update(result)
            except Exception:
                logger.exception(
                    f"Hook handler error: plugin={entry.plugin_name}, event={event}"
                )
        return current
