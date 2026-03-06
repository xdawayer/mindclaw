# input: mindclaw.tools
# output: 工具基类和注册表测试
# pos: 工具层测试入口
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


def test_tool_base_is_abstract():
    from mindclaw.tools.base import Tool
    with pytest.raises(TypeError):
        Tool()


def test_tool_subclass_requires_fields():
    from mindclaw.tools.base import RiskLevel, Tool

    class MyTool(Tool):
        name = "my_tool"
        description = "A test tool"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE

        async def execute(self, params: dict) -> str:
            return "ok"

    tool = MyTool()
    assert tool.name == "my_tool"
    assert tool.risk_level == RiskLevel.SAFE


def test_registry_register_and_get():
    from mindclaw.tools.base import RiskLevel, Tool
    from mindclaw.tools.registry import ToolRegistry

    class FakeTool(Tool):
        name = "fake"
        description = "fake tool"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE
        async def execute(self, params: dict) -> str:
            return "fake result"

    registry = ToolRegistry()
    registry.register(FakeTool())
    assert registry.get("fake") is not None
    assert registry.get("nonexistent") is None


def test_registry_get_all_tools():
    from mindclaw.tools.base import RiskLevel, Tool
    from mindclaw.tools.registry import ToolRegistry

    class ToolA(Tool):
        name = "tool_a"
        description = "A"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.SAFE
        async def execute(self, params): return "a"

    class ToolB(Tool):
        name = "tool_b"
        description = "B"
        parameters = {"type": "object", "properties": {}}
        risk_level = RiskLevel.MODERATE
        async def execute(self, params): return "b"

    registry = ToolRegistry()
    registry.register(ToolA())
    registry.register(ToolB())
    assert len(registry.all()) == 2


def test_registry_to_openai_schema():
    from mindclaw.tools.base import RiskLevel, Tool
    from mindclaw.tools.registry import ToolRegistry

    class ReadFile(Tool):
        name = "read_file"
        description = "Read a file"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"],
        }
        risk_level = RiskLevel.SAFE
        async def execute(self, params): return "content"

    registry = ToolRegistry()
    registry.register(ReadFile())
    schemas = registry.to_openai_tools()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "read_file"
