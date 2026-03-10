# input: mindclaw.tools.base
# output: 导出 HelloTool
# pos: 示例插件入口，演示如何定义自定义工具
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from mindclaw.tools.base import RiskLevel, Tool


class HelloTool(Tool):
    """A simple greeting tool for demonstration purposes."""

    name = "hello"
    description = "Say hello to someone by name"
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name to greet",
            },
        },
        "required": ["name"],
    }
    risk_level = RiskLevel.SAFE

    async def execute(self, params: dict) -> str:
        target = params.get("name", "World")
        return f"Hello, {target}!"
