# input: mindclaw.app, mindclaw.plugins.*
# output: 插件系统端到端集成测试
# pos: 验证插件加载、工具注册、hook 触发的完整流程
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""End-to-end tests for the plugin system integration."""

import json
import textwrap

import pytest

from mindclaw.config.schema import MindClawConfig
from mindclaw.plugins.hooks import HookRegistry
from mindclaw.plugins.loader import PluginLoader
from mindclaw.tools.registry import ToolRegistry


def _create_tool_plugin(plugins_dir, name="test_tool_plugin"):
    """Create a plugin directory with a custom tool."""
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": "Test tool plugin",
        "tools": ["PingTool"],
    }
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
    (plugin_dir / "main.py").write_text(textwrap.dedent("""\
        from mindclaw.tools.base import RiskLevel, Tool

        class PingTool(Tool):
            name = "ping"
            description = "Returns pong"
            parameters = {"type": "object", "properties": {}}
            risk_level = RiskLevel.SAFE

            async def execute(self, params: dict) -> str:
                return "pong"
    """))


def _create_hook_plugin(plugins_dir, name="test_hook_plugin"):
    """Create a plugin directory with hook handlers."""
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "0.1.0",
        "description": "Test hook plugin",
        "hooks": {
            "on_message": "hooks.on_message_handler",
            "before_tool": "hooks.before_tool_handler",
            "after_tool": "hooks.after_tool_handler",
        },
    }
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
    (plugin_dir / "main.py").write_text("# entry\n")
    (plugin_dir / "hooks.py").write_text(textwrap.dedent("""\
        _calls = []

        async def on_message_handler(**kwargs):
            _calls.append(("on_message", kwargs))

        async def before_tool_handler(**kwargs):
            _calls.append(("before_tool", kwargs))

        async def after_tool_handler(**kwargs):
            _calls.append(("after_tool", kwargs))
    """))


class TestPluginIntegration:
    """End-to-end plugin system tests."""

    @pytest.mark.asyncio
    async def test_full_plugin_load_and_use(self, tmp_path):
        """Load a plugin with tool, verify the tool is usable."""
        plugins_dir = tmp_path / "plugins"
        _create_tool_plugin(plugins_dir)

        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)

        assert "test_tool_plugin" in loaded
        tool = tool_registry.get("ping")
        assert tool is not None
        result = await tool.execute({})
        assert result == "pong"

    @pytest.mark.asyncio
    async def test_hook_plugin_registers_handlers(self, tmp_path):
        """Load a plugin with hooks, verify handlers registered."""
        plugins_dir = tmp_path / "plugins"
        _create_hook_plugin(plugins_dir)

        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        await loader.load_all(tool_registry, hook_registry)

        assert hook_registry.has_handlers("on_message")
        assert hook_registry.has_handlers("before_tool")
        assert hook_registry.has_handlers("after_tool")

    @pytest.mark.asyncio
    async def test_multiple_plugins_coexist(self, tmp_path):
        """Multiple plugins can load and register independently."""
        plugins_dir = tmp_path / "plugins"
        _create_tool_plugin(plugins_dir, name="plugin_a")
        _create_hook_plugin(plugins_dir, name="plugin_b")

        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)

        assert len(loaded) == 2
        assert tool_registry.get("ping") is not None
        assert hook_registry.has_handlers("on_message")

    @pytest.mark.asyncio
    async def test_plugin_tool_overrides_builtin(self, tmp_path):
        """Plugin tools can override built-in tools with same name."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "override"
        plugin_dir.mkdir(parents=True)
        manifest = {
            "name": "override",
            "version": "0.1.0",
            "description": "Override test",
            "tools": ["OverrideTool"],
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
        (plugin_dir / "main.py").write_text(textwrap.dedent("""\
            from mindclaw.tools.base import RiskLevel, Tool

            class OverrideTool(Tool):
                name = "read_file"
                description = "Overridden read_file"
                parameters = {"type": "object", "properties": {}}
                risk_level = RiskLevel.SAFE

                async def execute(self, params: dict) -> str:
                    return "overridden"
        """))

        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()

        # Register a "built-in" first
        from mindclaw.tools.base import RiskLevel, Tool

        class BuiltinReadFile(Tool):
            name = "read_file"
            description = "Built-in"
            parameters = {"type": "object", "properties": {}}
            risk_level = RiskLevel.SAFE

            async def execute(self, params: dict) -> str:
                return "builtin"

        tool_registry.register(BuiltinReadFile())

        # Load plugin - should override
        loader = PluginLoader(plugins_dir)
        await loader.load_all(tool_registry, hook_registry)

        tool = tool_registry.get("read_file")
        result = await tool.execute({})
        assert result == "overridden"

    @pytest.mark.asyncio
    async def test_app_has_hook_registry(self):
        """MindClawApp should have a hook_registry attribute."""
        from mindclaw.app import MindClawApp

        config = MindClawConfig()
        app = MindClawApp(config)
        assert hasattr(app, "hook_registry")
        assert isinstance(app.hook_registry, HookRegistry)

    @pytest.mark.asyncio
    async def test_app_loads_plugins_on_register_tools(self, tmp_path):
        """MindClawApp._register_tools should also load plugins."""
        from mindclaw.app import MindClawApp

        plugins_dir = tmp_path / "plugins"
        _create_tool_plugin(plugins_dir)

        config = MindClawConfig()
        app = MindClawApp(config)
        app._plugins_dir = plugins_dir
        app._register_tools()

        # Built-in tools should still exist
        assert app.tool_registry.get("read_file") is not None
        # Plugin tool should also be loaded
        assert app.tool_registry.get("ping") is not None
