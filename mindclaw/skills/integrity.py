# input: hashlib, ipaddress, socket, re
# output: 导出 compute_sha256, is_safe_download_url, validate_skill_content,
#         validate_skill_size, sanitize_approval_text, ValidationResult
# pos: 技能完整性校验，SHA256 / SSRF 过滤 / 格式验证 / 大小限制
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

"""Skill integrity: SHA256, SSRF filtering, format validation, size limits."""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r"^(\w+)\s*:\s*(.+)$")
_VALID_LOAD_MODES = frozenset({"on_demand", "always"})
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    name: str = ""
    description: str = ""
    load: str = "on_demand"
    error: str = ""


def compute_sha256(content: bytes) -> str:
    """Compute SHA256 hex digest of content."""
    return hashlib.sha256(content).hexdigest()


def is_safe_download_url(url: str) -> bool:
    """Check URL is HTTPS and does not target private/loopback/link-local/reserved IPs.

    Uses socket.getaddrinfo to resolve the hostname and ipaddress to classify
    the resulting addresses. Returns False for any non-public address.

    NOTE: There is a TOCTOU gap between this check and the actual HTTP request
    (DNS rebinding). httpx does not expose a hook to re-validate the resolved IP
    after connection. This is an accepted limitation shared with web.py; a full
    mitigation would require a custom transport or async resolver pinning.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        for _, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(sockaddr[0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
            ):
                return False
        return True
    except (socket.gaierror, ValueError, OSError):
        return False


def validate_skill_content(content: str) -> ValidationResult:
    """Validate skill markdown has valid YAML front-matter with required fields."""
    match = _FRONT_MATTER_RE.match(content)
    if not match:
        return ValidationResult(valid=False, error="No valid YAML front-matter found")

    front_matter = match.group(1)
    fields: dict[str, str] = {}
    for line in front_matter.strip().splitlines():
        line_match = _YAML_LINE_RE.match(line.strip())
        if line_match:
            fields[line_match.group(1)] = line_match.group(2).strip()

    name = fields.get("name", "")
    if not name:
        return ValidationResult(valid=False, error="Missing required field: name")

    description = fields.get("description", "")
    load = fields.get("load", "on_demand")
    if load not in _VALID_LOAD_MODES:
        return ValidationResult(
            valid=False,
            error=(
                f"Invalid load mode: '{load}'."
                f" Must be one of: {', '.join(sorted(_VALID_LOAD_MODES))}"
            ),
        )

    return ValidationResult(valid=True, name=name, description=description, load=load)


def validate_skill_size(content: bytes, *, max_size: int = 8192) -> bool:
    """Check if skill content is within the size limit (inclusive)."""
    return len(content) <= max_size


def sanitize_approval_text(text: str) -> str:
    """Remove control characters from text used in approval messages."""
    return _CONTROL_CHAR_RE.sub("", text).strip()
