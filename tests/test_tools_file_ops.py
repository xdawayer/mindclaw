# input: mindclaw.tools.file_ops
# output: 文件操作工具测试
# pos: 工具层文件操作测试
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import pytest


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "test.txt").write_text("hello world")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.txt").write_text("nested content")
    return tmp_path


@pytest.mark.asyncio
async def test_read_file(workspace):
    from mindclaw.tools.file_ops import ReadFileTool
    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "test.txt"})
    assert "hello world" in result


@pytest.mark.asyncio
async def test_read_file_not_found(workspace):
    from mindclaw.tools.file_ops import ReadFileTool
    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "nonexistent.txt"})
    assert "not found" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
async def test_read_file_path_traversal(workspace):
    from mindclaw.tools.file_ops import ReadFileTool
    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "../../etc/passwd"})
    assert "denied" in result.lower() or "outside" in result.lower()


@pytest.mark.asyncio
async def test_read_file_sibling_prefix_bypass(tmp_path):
    """Sibling dir with same prefix should be denied (e.g. /project vs /project-evil)."""
    from mindclaw.tools.file_ops import ReadFileTool

    workspace = tmp_path / "project"
    workspace.mkdir()
    sibling = tmp_path / "project-evil"
    sibling.mkdir()
    secret = sibling / "secret.txt"
    secret.write_text("top secret")

    tool = ReadFileTool(workspace=workspace)
    result = await tool.execute({"path": "../project-evil/secret.txt"})
    assert "denied" in result.lower() or "outside" in result.lower()


@pytest.mark.asyncio
async def test_write_file(workspace):
    from mindclaw.tools.file_ops import WriteFileTool
    tool = WriteFileTool(workspace=workspace)
    result = await tool.execute({"path": "new.txt", "content": "new content"})
    assert "success" in result.lower() or "written" in result.lower()
    assert (workspace / "new.txt").read_text() == "new content"


@pytest.mark.asyncio
async def test_write_file_creates_dirs(workspace):
    from mindclaw.tools.file_ops import WriteFileTool
    tool = WriteFileTool(workspace=workspace)
    await tool.execute({"path": "deep/nested/file.txt", "content": "deep"})
    assert (workspace / "deep" / "nested" / "file.txt").read_text() == "deep"


@pytest.mark.asyncio
async def test_list_dir(workspace):
    from mindclaw.tools.file_ops import ListDirTool
    tool = ListDirTool(workspace=workspace)
    result = await tool.execute({"path": "."})
    assert "test.txt" in result
    assert "subdir" in result


@pytest.mark.asyncio
async def test_edit_file(workspace):
    from mindclaw.tools.file_ops import EditFileTool
    tool = EditFileTool(workspace=workspace)
    result = await tool.execute({
        "path": "test.txt",
        "old_text": "hello world",
        "new_text": "hello mindclaw",
    })
    assert "success" in result.lower() or "edited" in result.lower()
    assert (workspace / "test.txt").read_text() == "hello mindclaw"


@pytest.mark.asyncio
async def test_edit_file_preserves_permissions(workspace):
    """Atomic write should preserve existing file permissions."""
    import os
    import stat

    from mindclaw.tools.file_ops import EditFileTool

    script = workspace / "run.sh"
    script.write_text("#!/bin/sh\necho hello")
    os.chmod(script, 0o755)

    tool = EditFileTool(workspace=workspace)
    await tool.execute({
        "path": "run.sh",
        "old_text": "echo hello",
        "new_text": "echo world",
    })

    mode = stat.S_IMODE(script.stat().st_mode)
    assert mode & 0o111, f"Execute bit lost: {oct(mode)}"
    assert script.read_text() == "#!/bin/sh\necho world"
