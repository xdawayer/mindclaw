# input: mindclaw.orchestrator.context
# output: ContextBuilder 测试
# pos: 验证系统提示动态构建
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from unittest.mock import MagicMock

from mindclaw.orchestrator.context import ContextBuilder


def test_build_system_prompt_without_memory():
    """System prompt should work even without any memory."""
    mm = MagicMock()
    mm.load_memory.return_value = ""
    builder = ContextBuilder(memory_manager=mm)
    prompt = builder.build_system_prompt()
    assert "MindClaw" in prompt
    assert "Current Date" in prompt


def test_build_system_prompt_with_memory():
    """System prompt includes memory when available."""
    mm = MagicMock()
    mm.load_memory.return_value = "# MindClaw Memory\n\n## 用户偏好\n- likes Python\n"
    builder = ContextBuilder(memory_manager=mm)
    prompt = builder.build_system_prompt()
    assert "MindClaw" in prompt
    assert "likes Python" in prompt
    assert "Memory" in prompt


def test_build_system_prompt_has_date():
    """System prompt includes current date."""
    import re

    mm = MagicMock()
    mm.load_memory.return_value = ""
    builder = ContextBuilder(memory_manager=mm)
    prompt = builder.build_system_prompt()
    assert re.search(r"\d{4}-\d{2}-\d{2}", prompt)
