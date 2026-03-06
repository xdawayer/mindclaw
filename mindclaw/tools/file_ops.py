# input: tools/base.py, pathlib
# output: 导出 ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
# pos: 文件操作工具集，带路径沙箱保护
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

from pathlib import Path

from .base import RiskLevel, Tool


def _safe_resolve(workspace: Path, relative_path: str) -> Path | None:
    """Resolve a relative path within a workspace, blocking traversal attacks."""
    try:
        target = (workspace / relative_path).resolve()
        if not str(target).startswith(str(workspace.resolve())):
            return None
        return target
    except (ValueError, OSError):
        return None


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
        },
        "required": ["path"],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: file not found: {params['path']}"
        if not target.is_file():
            return f"Error: not a file: {params['path']}"
        try:
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Path is relative to workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(params["content"], encoding="utf-8")
            return f"Successfully written to {params['path']}"
        except Exception as e:
            return f"Error writing file: {e}"


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Edit a file by replacing old_text with new_text. "
        "Path is relative to workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "old_text": {"type": "string", "description": "Text to find"},
            "new_text": {"type": "string", "description": "Replacement text"},
        },
        "required": ["path", "old_text", "new_text"],
    }
    risk_level = RiskLevel.MODERATE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        target = _safe_resolve(self.workspace, params["path"])
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: file not found: {params['path']}"
        try:
            content = target.read_text(encoding="utf-8")
            if params["old_text"] not in content:
                return f"Error: old_text not found in {params['path']}"
            new_content = content.replace(params["old_text"], params["new_text"], 1)
            target.write_text(new_content, encoding="utf-8")
            return f"Successfully edited {params['path']}"
        except Exception as e:
            return f"Error editing file: {e}"


class ListDirTool(Tool):
    name = "list_dir"
    description = "List contents of a directory. Path is relative to workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative directory path (default: '.')",
            },
        },
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, params: dict) -> str:
        rel_path = params.get("path", ".")
        target = _safe_resolve(self.workspace, rel_path)
        if target is None:
            return "Error: path denied - outside workspace"
        if not target.exists():
            return f"Error: directory not found: {rel_path}"
        if not target.is_dir():
            return f"Error: not a directory: {rel_path}"
        try:
            entries = sorted(target.iterdir())
            lines = []
            for entry in entries:
                suffix = "/" if entry.is_dir() else ""
                lines.append(f"  {entry.name}{suffix}")
            return f"Contents of {rel_path}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing directory: {e}"
