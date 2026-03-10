# input: plugins/manifest.py, plugins/hooks.py, plugins/exceptions.py,
#        tools/registry.py, importlib, pathlib
# output: 导出 PluginLoader
# pos: 插件发现与动态加载器，扫描 plugins/ 目录并注册工具/hook
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from loguru import logger

from mindclaw.plugins.exceptions import PluginLoadError, PluginManifestError
from mindclaw.plugins.hooks import HookRegistry
from mindclaw.plugins.manifest import PluginManifest
from mindclaw.tools.base import Tool
from mindclaw.tools.registry import ToolRegistry


class PluginLoader:
    """Discovers and loads plugins from a directory."""

    def __init__(self, plugins_dir: Path) -> None:
        self._plugins_dir = plugins_dir

    def discover(self) -> list[PluginManifest]:
        """Scan plugins directory and return valid manifests, sorted by name."""
        if not self._plugins_dir.is_dir():
            return []

        manifests: list[PluginManifest] = []
        for child in sorted(self._plugins_dir.iterdir()):
            if not child.is_dir():
                continue
            manifest_file = child / "manifest.json"
            if not manifest_file.exists():
                continue
            try:
                manifest = PluginManifest.from_file(manifest_file)
                manifests.append(manifest)
            except PluginManifestError:
                logger.warning(f"Skipping invalid plugin: {child.name}")
        return manifests

    async def load_all(
        self,
        tool_registry: ToolRegistry,
        hook_registry: HookRegistry,
    ) -> list[str]:
        """Discover and load all plugins, returning list of loaded plugin names."""
        manifests = self.discover()
        loaded: list[str] = []
        for manifest in manifests:
            try:
                self.load_one(manifest, tool_registry, hook_registry)
                loaded.append(manifest.name)
                logger.info(f"Loaded plugin: {manifest.name} v{manifest.version}")
            except PluginLoadError:
                logger.warning(f"Failed to load plugin: {manifest.name}")
        return loaded

    def _validate_path_confined(self, file_path: Path, label: str) -> None:
        """Ensure a resolved path stays within the plugins directory."""
        resolved = file_path.resolve()
        plugins_resolved = self._plugins_dir.resolve()
        if not resolved.is_relative_to(plugins_resolved):
            raise PluginLoadError(
                f"Path traversal detected in {label}: {file_path} "
                f"resolves outside {plugins_resolved}"
            )

    def load_one(
        self,
        manifest: PluginManifest,
        tool_registry: ToolRegistry,
        hook_registry: HookRegistry,
    ) -> None:
        """Load a single plugin: import module, register tools and hooks."""
        plugin_dir = self._plugins_dir / manifest.name
        entry_path = plugin_dir / manifest.entry

        # Path traversal protection
        self._validate_path_confined(entry_path, f"entry '{manifest.entry}'")

        # Import entry module
        entry_module = self._import_module(
            f"mindclaw_plugin_{manifest.name}", entry_path
        )
        if entry_module is None:
            raise PluginLoadError(f"Failed to import entry module: {entry_path}")

        # Register tools
        for tool_class_name in manifest.tools:
            cls = getattr(entry_module, tool_class_name, None)
            if cls is None:
                logger.warning(
                    f"Plugin '{manifest.name}': tool class '{tool_class_name}' not found"
                )
                continue
            if not (isinstance(cls, type) and issubclass(cls, Tool)):
                logger.warning(
                    f"Plugin '{manifest.name}': '{tool_class_name}' is not a Tool subclass"
                )
                continue
            tool_registry.register(cls())

        # Register hooks
        for event, handler_ref in manifest.hooks.items():
            try:
                handler = self._resolve_hook_handler(manifest.name, plugin_dir, handler_ref)
            except PluginLoadError as e:
                logger.warning(f"Plugin '{manifest.name}': {e}")
                continue
            if handler is None:
                logger.warning(
                    f"Plugin '{manifest.name}': hook handler '{handler_ref}' not found"
                )
                continue
            hook_registry.register(event, manifest.name, handler)

    def _resolve_hook_handler(
        self, plugin_name: str, plugin_dir: Path, handler_ref: str
    ):
        """Resolve a hook handler reference like 'hooks.on_message_handler'.

        Format: 'module_name.function_name'
        """
        parts = handler_ref.rsplit(".", 1)
        if len(parts) != 2:
            return None

        module_name, func_name = parts
        module_path = plugin_dir / f"{module_name}.py"

        # Path traversal protection
        self._validate_path_confined(module_path, f"hook module '{module_name}'")

        module = self._import_module(
            f"mindclaw_plugin_{plugin_name}_{module_name}", module_path
        )
        if module is None:
            return None

        handler = getattr(module, func_name, None)
        if handler is None or not callable(handler):
            return None
        return handler

    @staticmethod
    def _import_module(module_name: str, file_path: Path) -> ModuleType | None:
        """Dynamically import a Python module from a file path."""
        if not file_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return module
        except Exception:
            logger.exception(f"Failed to import module: {file_path}")
            # Clean up partial registration
            sys.modules.pop(module_name, None)
            return None
