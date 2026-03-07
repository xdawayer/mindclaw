# input: re, pathlib
# output: 导出 is_command_denied, validate_path, DENY_PATTERNS
# pos: 安全层沙箱核心，集中管理命令黑名单和路径验证
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import re
from pathlib import Path

# Best-effort heuristic blocklist; real security boundary is the DANGEROUS risk level gate
DENY_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=",
    r"mkfs\.",
    r":\(\)\{.*\}",
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777\s+/",
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
]

_compiled_deny = [re.compile(p) for p in DENY_PATTERNS]


def is_command_denied(command: str) -> bool:
    """Check if a command matches the deny-list patterns."""
    for pattern in _compiled_deny:
        if pattern.search(command):
            return True
    return False


def validate_path(workspace: Path, relative_path: str) -> Path | None:
    """Resolve a relative path within workspace, blocking traversal and symlink escapes."""
    try:
        target = (workspace / relative_path).resolve()
        if not target.is_relative_to(workspace.resolve()):
            return None
        return target
    except (ValueError, OSError):
        return None
