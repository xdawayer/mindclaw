# input: loguru
# output: 导出 before_tool_handler, after_tool_handler
# pos: 示例 hook 处理器，演示 before_tool/after_tool 用法
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from loguru import logger


async def before_tool_handler(**kwargs):
    """Log tool invocation before execution."""
    tool_name = kwargs.get("tool_name", "unknown")
    logger.debug(f"[hello_world] before_tool: {tool_name}")


async def after_tool_handler(**kwargs):
    """Log tool result after execution."""
    tool_name = kwargs.get("tool_name", "unknown")
    result = kwargs.get("result", "")
    logger.debug(f"[hello_world] after_tool: {tool_name} -> {result[:100]}")
