# input: mindclaw.plugins.manifest, mindclaw.plugins.exceptions
# output: manifest 模型解析和验证测试
# pos: 插件 manifest 测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for plugin manifest parsing and validation."""

import json

import pytest

from mindclaw.plugins.exceptions import PluginManifestError
from mindclaw.plugins.manifest import PluginManifest


class TestPluginManifest:
    """Test PluginManifest model parsing and validation."""

    def test_minimal_valid_manifest(self):
        data = {"name": "test-plugin", "version": "0.1.0", "description": "A test plugin"}
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "test-plugin"
        assert manifest.version == "0.1.0"
        assert manifest.description == "A test plugin"
        assert manifest.author == ""
        assert manifest.entry == "main.py"
        assert manifest.tools == ()
        assert manifest.channels == ()
        assert manifest.hooks == {}

    def test_full_manifest(self):
        data = {
            "name": "full-plugin",
            "version": "1.2.3",
            "description": "Full featured plugin",
            "author": "wzb",
            "entry": "plugin.py",
            "tools": ["MyTool", "AnotherTool"],
            "channels": ["MyChannel"],
            "hooks": {
                "before_tool": "hooks.before_tool_handler",
                "on_message": "hooks.on_message_handler",
            },
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.name == "full-plugin"
        assert manifest.author == "wzb"
        assert manifest.entry == "plugin.py"
        assert manifest.tools == ("MyTool", "AnotherTool")
        assert manifest.channels == ("MyChannel",)
        assert manifest.hooks == {
            "before_tool": "hooks.before_tool_handler",
            "on_message": "hooks.on_message_handler",
        }

    def test_missing_name_raises(self):
        data = {"version": "0.1.0", "description": "No name"}
        with pytest.raises(PluginManifestError, match="name"):
            PluginManifest.from_dict(data)

    def test_missing_version_raises(self):
        data = {"name": "test", "description": "No version"}
        with pytest.raises(PluginManifestError, match="version"):
            PluginManifest.from_dict(data)

    def test_missing_description_raises(self):
        data = {"name": "test", "version": "0.1.0"}
        with pytest.raises(PluginManifestError, match="description"):
            PluginManifest.from_dict(data)

    def test_invalid_hook_name_raises(self):
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "Bad hook",
            "hooks": {"invalid_hook_event": "handler.func"},
        }
        with pytest.raises(PluginManifestError, match="invalid_hook_event"):
            PluginManifest.from_dict(data)

    def test_valid_hook_names(self):
        valid_hooks = [
            "on_message", "before_tool", "after_tool",
            "on_reply", "on_error", "on_start", "on_stop",
        ]
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "All hooks",
            "hooks": {h: f"hooks.{h}_handler" for h in valid_hooks},
        }
        manifest = PluginManifest.from_dict(data)
        assert len(manifest.hooks) == 7

    def test_from_json_file(self, tmp_path):
        manifest_data = {
            "name": "file-plugin",
            "version": "0.1.0",
            "description": "From file",
        }
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        manifest = PluginManifest.from_file(manifest_file)
        assert manifest.name == "file-plugin"

    def test_from_invalid_json_file(self, tmp_path):
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text("not valid json {{{")
        with pytest.raises(PluginManifestError, match="JSON"):
            PluginManifest.from_file(manifest_file)

    def test_from_nonexistent_file(self, tmp_path):
        manifest_file = tmp_path / "does_not_exist.json"
        with pytest.raises(PluginManifestError, match="not found"):
            PluginManifest.from_file(manifest_file)

    def test_empty_tools_and_channels(self):
        data = {
            "name": "empty",
            "version": "0.1.0",
            "description": "Empty lists",
            "tools": [],
            "channels": [],
            "hooks": {},
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.tools == ()
        assert manifest.channels == ()
        assert manifest.hooks == {}

    def test_tools_must_be_list_of_strings(self):
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "Bad tools",
            "tools": [123],
        }
        with pytest.raises(PluginManifestError, match="tools"):
            PluginManifest.from_dict(data)

    def test_hooks_values_must_be_strings(self):
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "Bad hooks",
            "hooks": {"on_message": 123},
        }
        with pytest.raises(PluginManifestError, match="hooks"):
            PluginManifest.from_dict(data)

    def test_channels_must_be_list_of_strings(self):
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "Bad channels",
            "channels": [123],
        }
        with pytest.raises(PluginManifestError, match="channels"):
            PluginManifest.from_dict(data)

    def test_channels_string_not_list_raises(self):
        data = {
            "name": "test",
            "version": "0.1.0",
            "description": "Bad channels",
            "channels": "not-a-list",
        }
        with pytest.raises(PluginManifestError, match="channels"):
            PluginManifest.from_dict(data)

    def test_hooks_is_immutable(self):
        data = {"name": "test", "version": "0.1.0", "description": "Immutable hooks",
                "hooks": {"on_message": "hooks.handler"}}
        manifest = PluginManifest.from_dict(data)
        with pytest.raises(TypeError):
            manifest.hooks["on_error"] = "hooks.error_handler"
