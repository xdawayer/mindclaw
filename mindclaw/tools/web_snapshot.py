# input: tools/base.py, tools/_ssrf.py, httpx, uuid, json
# output: WebSnapshotTool, WebSnapshotListTool, WebSnapshotReadTool
# pos: 网页快照工具，保存/列出/读取网页快照用于竞品监控
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx
from loguru import logger

from ._ssrf import is_safe_url as _is_safe_url
from .base import RiskLevel, Tool

_MAX_RESPONSE_BYTES = 2_000_000
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_MAX_REDIRECTS = 5


class WebSnapshotTool(Tool):
    name = "web_snapshot"
    description = "Save a snapshot of a web page for later comparison"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to snapshot"},
        },
        "required": ["url"],
    }
    risk_level = RiskLevel.MODERATE
    max_result_chars = 500

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._snapshots_dir = data_dir / "snapshots"

    async def execute(self, params: dict) -> str:
        url = params["url"]
        if not _is_safe_url(url):
            return "Error: URL targets a private/internal address"

        logger.info(f"Snapshotting: {url}")
        try:
            body = await _fetch_bytes(url)
        except Exception as exc:
            return f"Error fetching URL: {exc}"

        snap_id = str(uuid.uuid4())
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        snap_file = self._snapshots_dir / f"{snap_id}.txt"
        snap_file.write_bytes(body)

        entry = {
            "id": snap_id,
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size": len(body),
        }
        index_path = self._snapshots_dir / "index.jsonl"
        with index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

        return f"Snapshot saved: {snap_id} ({len(body)} bytes)"


class WebSnapshotListTool(Tool):
    name = "web_snapshot_list"
    description = "List recent snapshots, optionally filtered by URL"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Filter by URL (optional)"},
            "limit": {"type": "integer", "description": "Max entries to return (default 10)"},
        },
        "required": [],
    }
    risk_level = RiskLevel.SAFE

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._snapshots_dir = data_dir / "snapshots"

    async def execute(self, params: dict) -> str:
        url_filter = params.get("url")
        try:
            limit = int(params.get("limit", 10))
        except (TypeError, ValueError):
            return "Error: 'limit' must be an integer"

        index_path = self._snapshots_dir / "index.jsonl"
        if not index_path.exists():
            return "No snapshots found."

        entries = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if url_filter:
            entries = [e for e in entries if e.get("url") == url_filter]

        # Most recent first (reverse insertion order)
        entries = list(reversed(entries))[:limit]

        if not entries:
            return "No snapshots found."

        lines = [
            f"- {e['id']}: {e['url']} ({e['timestamp']}, {e['size']} bytes)"
            for e in entries
        ]
        return "\n".join(lines)


class WebSnapshotReadTool(Tool):
    name = "web_snapshot_read"
    description = "Read the content of a saved snapshot by ID"
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Snapshot UUID"},
        },
        "required": ["id"],
    }
    risk_level = RiskLevel.SAFE
    max_result_chars = 5000

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._snapshots_dir = data_dir / "snapshots"

    async def execute(self, params: dict) -> str:
        snap_id = params["id"]

        # Validate UUID format to prevent path traversal
        try:
            parsed = uuid.UUID(snap_id)
        except ValueError:
            return f"Error: invalid snapshot ID '{snap_id}'"

        # Use the canonical form (no path separators possible)
        safe_id = str(parsed)
        snap_file = self._snapshots_dir / f"{safe_id}.txt"

        if not snap_file.exists():
            return f"Error: snapshot {safe_id} not found"

        content = snap_file.read_text(encoding="utf-8", errors="replace")
        if self.max_result_chars and len(content) > self.max_result_chars:
            content = content[: self.max_result_chars] + "\n...(truncated)"
        return content


# ---------------------------------------------------------------------------
# Internal fetch helper (manual redirect following with SSRF re-check)
# ---------------------------------------------------------------------------


async def _fetch_bytes(url: str) -> bytes:
    """Fetch URL content as raw bytes, following redirects safely."""
    async with httpx.AsyncClient(
        follow_redirects=False, timeout=15.0, trust_env=False
    ) as client:
        current_url = url
        body = bytearray()
        for _ in range(_MAX_REDIRECTS):
            async with client.stream("GET", current_url) as resp:
                if resp.status_code in _REDIRECT_CODES:
                    location = resp.headers.get("location")
                    if not location:
                        raise RuntimeError("redirect with no Location header")
                    current_url = urljoin(current_url, location)
                    if not _is_safe_url(current_url):
                        raise RuntimeError("redirect targets a private/internal address")
                    continue
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_RESPONSE_BYTES:
                        break
            return bytes(body)
        raise RuntimeError("too many redirects")
