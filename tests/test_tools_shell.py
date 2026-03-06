# input: mindclaw.tools.shell
# output: Shell 工具测试
# pos: 工具层 Shell 执行测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


@pytest.mark.asyncio
async def test_exec_simple_command(tmp_path):
    from mindclaw.tools.shell import ExecTool
    tool = ExecTool(workspace=tmp_path, timeout=10)
    result = await tool.execute({"command": "echo hello"})
    assert "hello" in result


@pytest.mark.asyncio
async def test_exec_deny_pattern():
    from pathlib import Path

    from mindclaw.tools.shell import ExecTool
    tool = ExecTool(workspace=Path("/tmp"), timeout=10)
    result = await tool.execute({"command": "rm -rf /"})
    assert "denied" in result.lower() or "blocked" in result.lower()


@pytest.mark.asyncio
async def test_exec_deny_fork_bomb():
    from pathlib import Path

    from mindclaw.tools.shell import ExecTool
    tool = ExecTool(workspace=Path("/tmp"), timeout=10)
    result = await tool.execute({"command": ":(){ :|:& };:"})
    assert "denied" in result.lower() or "blocked" in result.lower()


@pytest.mark.asyncio
async def test_exec_timeout(tmp_path):
    from mindclaw.tools.shell import ExecTool
    tool = ExecTool(workspace=tmp_path, timeout=1)
    result = await tool.execute({"command": "sleep 10"})
    assert "timeout" in result.lower()


@pytest.mark.asyncio
async def test_exec_returns_stderr(tmp_path):
    from mindclaw.tools.shell import ExecTool
    tool = ExecTool(workspace=tmp_path, timeout=10)
    result = await tool.execute({"command": "ls /nonexistent_dir_12345"})
    assert len(result) > 0
