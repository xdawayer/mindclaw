# input: mindclaw.plugins.loader
# output: 插件发现、加载、注册测试
# pos: 插件加载器测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for plugin discovery, loading, and registration."""

import json
import textwrap

import pytest

from mindclaw.plugins.hooks import HookRegistry
from mindclaw.plugins.loader import PluginLoader
from mindclaw.tools.registry import ToolRegistry


def _write_plugin(plugin_dir, manifest_data, module_code, hook_code=None):
    """Helper to create a plugin directory with manifest and code."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "manifest.json").write_text(json.dumps(manifest_data))
    (plugin_dir / manifest_data.get("entry", "main.py")).write_text(
        textwrap.dedent(module_code)
    )
    if hook_code:
        (plugin_dir / "hooks.py").write_text(textwrap.dedent(hook_code))


class TestPluginLoader:
    """Test PluginLoader discovery and loading."""

    def test_discover_empty_directory(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        loader = PluginLoader(plugins_dir)
        manifests = loader.discover()
        assert manifests == []

    def test_discover_directory_without_manifest(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        (plugins_dir / "not-a-plugin").mkdir(parents=True)
        (plugins_dir / "not-a-plugin" / "random.py").write_text("x = 1")
        loader = PluginLoader(plugins_dir)
        manifests = loader.discover()
        assert manifests == []

    def test_discover_valid_plugin(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "hello",
            {"name": "hello", "version": "0.1.0", "description": "Hello plugin"},
            "# empty module\n",
        )
        loader = PluginLoader(plugins_dir)
        manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "hello"

    def test_discover_multiple_plugins_sorted(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        for name in ["charlie", "alpha", "bravo"]:
            _write_plugin(
                plugins_dir / name,
                {"name": name, "version": "0.1.0", "description": f"{name} plugin"},
                "# empty\n",
            )
        loader = PluginLoader(plugins_dir)
        manifests = loader.discover()
        assert [m.name for m in manifests] == ["alpha", "bravo", "charlie"]

    def test_discover_skips_invalid_manifest(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        # Valid plugin
        _write_plugin(
            plugins_dir / "good",
            {"name": "good", "version": "0.1.0", "description": "Good"},
            "# ok\n",
        )
        # Invalid plugin (missing name)
        bad_dir = plugins_dir / "bad"
        bad_dir.mkdir(parents=True)
        (bad_dir / "manifest.json").write_text(json.dumps({"version": "0.1.0"}))
        loader = PluginLoader(plugins_dir)
        manifests = loader.discover()
        assert len(manifests) == 1
        assert manifests[0].name == "good"

    def test_discover_nonexistent_directory(self, tmp_path):
        loader = PluginLoader(tmp_path / "nonexistent")
        manifests = loader.discover()
        assert manifests == []

    @pytest.mark.asyncio
    async def test_load_plugin_with_tool(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "greeter",
            {
                "name": "greeter",
                "version": "0.1.0",
                "description": "Greeter",
                "tools": ["GreetTool"],
            },
            '''\
            from mindclaw.tools.base import RiskLevel, Tool

            class GreetTool(Tool):
                name = "greet"
                description = "Say hello"
                parameters = {"type": "object", "properties": {}}
                risk_level = RiskLevel.SAFE

                async def execute(self, params: dict) -> str:
                    return "hello!"
            ''',
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        assert len(loaded) == 1
        assert tool_registry.get("greet") is not None

    @pytest.mark.asyncio
    async def test_load_plugin_with_hook(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "logger_plugin",
            {
                "name": "logger_plugin",
                "version": "0.1.0",
                "description": "Logger",
                "hooks": {"on_message": "hooks.on_message_handler"},
            },
            "# entry\n",
            hook_code='''\
            async def on_message_handler(**kwargs):
                pass
            ''',
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        assert len(loaded) == 1
        assert hook_registry.has_handlers("on_message")

    @pytest.mark.asyncio
    async def test_load_plugin_with_bad_module_skips(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "broken",
            {
                "name": "broken",
                "version": "0.1.0",
                "description": "Broken",
                "tools": ["NonExistent"],
            },
            "raise ImportError('deliberate')\n",
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_load_plugin_tool_not_found_skips(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "missing_tool",
            {
                "name": "missing_tool",
                "version": "0.1.0",
                "description": "Missing tool class",
                "tools": ["DoesNotExist"],
            },
            "x = 1  # no tool class here\n",
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        # Plugin loads but the tool is skipped
        assert len(loaded) == 1
        assert tool_registry.get("DoesNotExist") is None

    @pytest.mark.asyncio
    async def test_load_plugin_hook_handler_not_found_skips(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "bad_hook",
            {
                "name": "bad_hook",
                "version": "0.1.0",
                "description": "Bad hook ref",
                "hooks": {"on_message": "hooks.nonexistent_func"},
            },
            "# entry\n",
            hook_code="# no handler here\n",
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        assert len(loaded) == 1
        assert not hook_registry.has_handlers("on_message")

    @pytest.mark.asyncio
    async def test_path_traversal_in_entry_blocked(self, tmp_path):
        """Plugin with path traversal in entry field should be rejected."""
        plugins_dir = tmp_path / "plugins"
        plugin_dir = plugins_dir / "evil"
        plugin_dir.mkdir(parents=True)
        manifest = {
            "name": "evil",
            "version": "0.1.0",
            "description": "Evil plugin",
            "entry": "../../etc/passwd",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest))
        # Create a real target file outside plugins dir to ensure it's the
        # path check (not FileNotFoundError) that blocks loading
        target = tmp_path / "etc"
        target.mkdir(parents=True, exist_ok=True)
        (target / "passwd").write_text("x = 1\n")

        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_path_traversal_in_hook_ref_blocked(self, tmp_path):
        """Plugin with path traversal in hook module reference should be rejected."""
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "evil_hook",
            {
                "name": "evil_hook",
                "version": "0.1.0",
                "description": "Evil hook",
                "hooks": {"on_message": "../../evil.handler"},
            },
            "# entry\n",
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        loaded = await loader.load_all(tool_registry, hook_registry)
        # Plugin loads but the hook with traversal path is rejected
        assert len(loaded) == 1
        assert not hook_registry.has_handlers("on_message")

    @pytest.mark.asyncio
    async def test_loaded_tool_is_executable(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        _write_plugin(
            plugins_dir / "echo",
            {
                "name": "echo",
                "version": "0.1.0",
                "description": "Echo",
                "tools": ["EchoTool"],
            },
            '''\
            from mindclaw.tools.base import RiskLevel, Tool

            class EchoTool(Tool):
                name = "echo"
                description = "Echo input"
                parameters = {"type": "object", "properties": {"text": {"type": "string"}}}
                risk_level = RiskLevel.SAFE

                async def execute(self, params: dict) -> str:
                    return params.get("text", "")
            ''',
        )
        tool_registry = ToolRegistry()
        hook_registry = HookRegistry()
        loader = PluginLoader(plugins_dir)
        await loader.load_all(tool_registry, hook_registry)
        tool = tool_registry.get("echo")
        assert tool is not None
        result = await tool.execute({"text": "ping"})
        assert result == "ping"
