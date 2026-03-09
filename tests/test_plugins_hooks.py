# input: mindclaw.plugins.hooks
# output: Hook 注册表和事件分发测试
# pos: 插件 hook 系统测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Tests for hook registry and event dispatching."""

import pytest

from mindclaw.plugins.hooks import HookRegistry


class TestHookRegistry:
    """Test HookRegistry registration and dispatch."""

    def test_register_handler(self):
        registry = HookRegistry()

        async def handler(**kwargs):
            pass

        registry.register("before_tool", "test-plugin", handler)
        assert registry.has_handlers("before_tool")

    def test_register_invalid_hook_raises(self):
        registry = HookRegistry()

        async def handler(**kwargs):
            pass

        with pytest.raises(ValueError, match="invalid_event"):
            registry.register("invalid_event", "test-plugin", handler)

    def test_has_handlers_false_when_empty(self):
        registry = HookRegistry()
        assert not registry.has_handlers("before_tool")

    @pytest.mark.asyncio
    async def test_call_single_handler(self):
        registry = HookRegistry()
        calls = []

        async def handler(**kwargs):
            calls.append(kwargs)

        registry.register("on_message", "test-plugin", handler)
        await registry.call("on_message", text="hello", channel="cli")
        assert len(calls) == 1
        assert calls[0] == {"text": "hello", "channel": "cli"}

    @pytest.mark.asyncio
    async def test_call_multiple_handlers_sequential(self):
        """Handlers execute in registration order."""
        registry = HookRegistry()
        order = []

        async def handler_a(**kwargs):
            order.append("a")

        async def handler_b(**kwargs):
            order.append("b")

        registry.register("on_message", "plugin-a", handler_a)
        registry.register("on_message", "plugin-b", handler_b)
        await registry.call("on_message", text="hi")
        assert order == ["a", "b"]

    @pytest.mark.asyncio
    async def test_call_no_handlers_is_noop(self):
        registry = HookRegistry()
        # Should not raise
        await registry.call("on_message", text="hi")

    @pytest.mark.asyncio
    async def test_before_tool_can_modify_params(self):
        """before_tool handlers can return modified params."""
        registry = HookRegistry()

        async def add_tag(**kwargs):
            params = dict(kwargs.get("params", {}))
            params["tag"] = "injected"
            return {"params": params}

        registry.register("before_tool", "tagger", add_tag)
        result = await registry.call_with_result(
            "before_tool", tool_name="read_file", params={"path": "/tmp"}
        )
        assert result["params"]["tag"] == "injected"
        assert result["params"]["path"] == "/tmp"

    @pytest.mark.asyncio
    async def test_call_with_result_chains_modifications(self):
        """Multiple handlers chain modifications through call_with_result."""
        registry = HookRegistry()

        async def handler_1(**kwargs):
            params = dict(kwargs.get("params", {}))
            params["step1"] = True
            return {"params": params}

        async def handler_2(**kwargs):
            params = dict(kwargs.get("params", {}))
            params["step2"] = True
            return {"params": params}

        registry.register("before_tool", "p1", handler_1)
        registry.register("before_tool", "p2", handler_2)
        result = await registry.call_with_result(
            "before_tool", tool_name="test", params={"original": True}
        )
        assert result["params"]["step1"] is True
        assert result["params"]["step2"] is True
        assert result["params"]["original"] is True

    @pytest.mark.asyncio
    async def test_call_with_result_handler_returns_none(self):
        """If handler returns None, kwargs pass through unchanged."""
        registry = HookRegistry()

        async def noop_handler(**kwargs):
            pass  # Returns None

        registry.register("before_tool", "noop", noop_handler)
        result = await registry.call_with_result(
            "before_tool", params={"key": "value"}
        )
        assert result["params"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handler_error_does_not_block(self):
        """A failing handler logs error but does not block other handlers."""
        registry = HookRegistry()
        calls = []

        async def bad_handler(**kwargs):
            raise RuntimeError("boom")

        async def good_handler(**kwargs):
            calls.append("good")

        registry.register("on_error", "bad", bad_handler)
        registry.register("on_error", "good", good_handler)
        # Should not raise
        await registry.call("on_error", error="something")
        assert calls == ["good"]

    @pytest.mark.asyncio
    async def test_handler_error_in_call_with_result_does_not_block(self):
        """A failing handler in call_with_result skips but continues chain."""
        registry = HookRegistry()

        async def bad_handler(**kwargs):
            raise RuntimeError("boom")

        async def good_handler(**kwargs):
            params = dict(kwargs.get("params", {}))
            params["good"] = True
            return {"params": params}

        registry.register("before_tool", "bad", bad_handler)
        registry.register("before_tool", "good", good_handler)
        result = await registry.call_with_result("before_tool", params={})
        assert result["params"]["good"] is True

    def test_unregister_plugin(self):
        registry = HookRegistry()

        async def handler(**kwargs):
            pass

        registry.register("on_message", "test-plugin", handler)
        assert registry.has_handlers("on_message")
        registry.unregister_plugin("test-plugin")
        assert not registry.has_handlers("on_message")

    def test_unregister_nonexistent_plugin_is_noop(self):
        registry = HookRegistry()
        # Should not raise
        registry.unregister_plugin("nonexistent")

    @pytest.mark.asyncio
    async def test_call_invalid_event_is_noop(self):
        """Calling a non-existent event should not raise."""
        registry = HookRegistry()
        await registry.call("on_start")
