# input: pathlib, json, plugins/exceptions.py
# output: 导出 PluginManifest, VALID_HOOK_NAMES
# pos: 插件 manifest.json 解析与验证模型
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from mindclaw.plugins.exceptions import PluginManifestError

VALID_HOOK_NAMES = frozenset({
    "on_message",
    "before_tool",
    "after_tool",
    "on_reply",
    "on_error",
    "on_start",
    "on_stop",
})


@dataclass(frozen=True)
class PluginManifest:
    """Immutable representation of a plugin's manifest.json."""

    name: str
    version: str
    description: str
    author: str = ""
    entry: str = "main.py"
    tools: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    hooks: Mapping[str, str] = MappingProxyType({})

    @classmethod
    def from_dict(cls, data: dict) -> PluginManifest:
        """Parse and validate a manifest dict, raising PluginManifestError on issues."""
        errors: list[str] = []

        for required in ("name", "version", "description"):
            if required not in data:
                errors.append(f"Missing required field: {required}")
        if errors:
            raise PluginManifestError("; ".join(errors))

        # Validate tools
        raw_tools = data.get("tools", [])
        if not isinstance(raw_tools, list) or not all(isinstance(t, str) for t in raw_tools):
            raise PluginManifestError("'tools' must be a list of strings")

        # Validate hooks
        raw_hooks = data.get("hooks", {})
        if not isinstance(raw_hooks, dict):
            raise PluginManifestError("'hooks' must be a dict")
        for key, val in raw_hooks.items():
            if not isinstance(val, str):
                raise PluginManifestError(
                    f"'hooks' values must be strings, got {type(val).__name__} for '{key}'"
                )
            if key not in VALID_HOOK_NAMES:
                raise PluginManifestError(
                    f"Invalid hook name: '{key}'. Valid: {sorted(VALID_HOOK_NAMES)}"
                )

        # Validate channels
        raw_channels = data.get("channels", [])
        if not isinstance(raw_channels, list) or not all(
            isinstance(c, str) for c in raw_channels
        ):
            raise PluginManifestError("'channels' must be a list of strings")

        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data.get("author", ""),
            entry=data.get("entry", "main.py"),
            tools=tuple(raw_tools),
            channels=tuple(raw_channels),
            hooks=MappingProxyType(dict(raw_hooks)),
        )

    @classmethod
    def from_file(cls, path: Path) -> PluginManifest:
        """Load manifest from a JSON file."""
        if not path.exists():
            raise PluginManifestError(f"Manifest file not found: {path}")
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise PluginManifestError(f"Invalid JSON in {path}: {e}") from e
        return cls.from_dict(data)
